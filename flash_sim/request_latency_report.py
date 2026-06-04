from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .common import Request, RequestType, Transaction


BASE_STAGE_NAMES = (
    "host_sq_wait",
    "host_dispatch",
    "pcie_host_to_device",
    "pcie_device_to_host",
    "amu_mapping_wait",
    "tsu_queue_wait",
    "phy_cmd_addr",
    "phy_data_in",
    "phy_array_exec",
    "phy_data_out",
)

RECONCILIATION_STAGE_NAMES = ("overlap_latency", "untracked_latency")


def _zero_breakdown() -> dict[str, int]:
    data = {stage: 0 for stage in BASE_STAGE_NAMES}
    data.update({stage: 0 for stage in RECONCILIATION_STAGE_NAMES})
    return data


def _merge_intervals(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if not intervals:
        return []
    ordered = sorted((min(start, end), max(start, end)) for start, end in intervals)
    merged: list[list[int]] = [[ordered[0][0], ordered[0][1]]]
    for start, end in ordered[1:]:
        if start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [(start, end) for start, end in merged]


def _merged_duration(intervals: list[tuple[int, int]]) -> int:
    return sum(end - start for start, end in _merge_intervals(intervals))


@dataclass
class RequestLatencyState:
    req_id: str
    trace_index: Optional[int]
    trace_time: Optional[int]
    req_type: str
    lha_start: Optional[int]
    size: Optional[int]
    stream_id: int
    sq_id: Optional[int]
    scheduled_time: Optional[int] = None
    req_init_time: Optional[int] = None
    sq_enter_time: Optional[int] = None
    first_host_send_time: Optional[int] = None
    host_completion_time: Optional[int] = None
    status: Optional[str] = None
    error_message: Optional[str] = None
    intervals: dict[str, list[dict[str, Any]]] = field(
        default_factory=lambda: {stage: [] for stage in BASE_STAGE_NAMES}
    )
    persistence_intervals: dict[str, list[dict[str, Any]]] = field(
        default_factory=lambda: {stage: [] for stage in BASE_STAGE_NAMES}
    )
    persistence_status: str = "not_applicable"
    persistence_completion_time: Optional[int] = None


class RequestLatencyRecorder:
    def __init__(self) -> None:
        self.engine = None
        self.trace_path: Optional[Path] = None
        self.requests: dict[str, RequestLatencyState] = {}
        self._pcie_messages: dict[int, dict[str, Any]] = {}
        self._mapping_waits: dict[tuple[str, str], int] = {}
        self._tsu_enqueue_times: dict[int, int] = {}
        self._tsu_dispatched: set[int] = set()

    def attach(self, engine: Any) -> None:
        self.engine = engine

    def set_trace_context(self, trace_path: str | Path) -> None:
        self.trace_path = Path(trace_path)

    def derive_report_path(self, root_dir: str | Path) -> Path:
        base_name = self.trace_path.stem if self.trace_path is not None else "request_latency"
        return Path(root_dir) / f"{base_name}_request_latency.json"

    def register_request(self, req: Request, scheduled_time: Optional[int] = None) -> None:
        rec = self._ensure_request(req)
        rec.scheduled_time = scheduled_time
        if req.type in (RequestType.WRITE, RequestType.STATIC_WRITE):
            rec.persistence_status = "pending_without_flush"

    def note_req_init_executed(self, req: Request, timestamp: int) -> None:
        rec = self._ensure_request(req)
        if rec.req_init_time is None:
            rec.req_init_time = timestamp

    def note_sq_entered(self, req: Request, timestamp: int) -> None:
        rec = self._ensure_request(req)
        if rec.sq_enter_time is None:
            rec.sq_enter_time = timestamp
        else:
            rec.sq_enter_time = min(rec.sq_enter_time, timestamp)
        if req.sq_id is not None:
            rec.sq_id = req.sq_id

    def note_host_sent(self, req: Request, timestamp: int) -> None:
        rec = self._ensure_request(req)
        if rec.first_host_send_time is not None:
            return
        rec.first_host_send_time = timestamp
        if rec.req_init_time is not None and timestamp > rec.req_init_time:
            self._append_interval(rec, "intervals", "host_dispatch", rec.req_init_time, timestamp, {"source": "host"})
        if rec.sq_enter_time is not None and timestamp > rec.sq_enter_time:
            self._append_interval(rec, "intervals", "host_sq_wait", rec.sq_enter_time, timestamp, {"source": "host"})

    def note_pcie_enqueued(
        self,
        message: Any,
        direction: str,
        timestamp: int,
        transfer_bytes: int,
    ) -> None:
        request_ids = self._request_ids_from_message(message)
        if not request_ids:
            return
        self._pcie_messages[id(message)] = {
            "direction": direction,
            "message_type": getattr(getattr(message, "type", None), "value", str(getattr(message, "type", ""))),
            "start": timestamp,
            "transfer_bytes": transfer_bytes,
            "request_ids": request_ids,
        }

    def note_pcie_delivered(self, message: Any, timestamp: int) -> None:
        info = self._pcie_messages.pop(id(message), None)
        if info is None:
            return
        stage = "pcie_host_to_device" if info["direction"] == "host_to_device" else "pcie_device_to_host"
        for req_id in info["request_ids"]:
            rec = self.requests.get(req_id)
            if rec is None:
                continue
            self._append_interval(
                rec,
                "intervals",
                stage,
                info["start"],
                timestamp,
                {
                    "source": "pcie",
                    "direction": info["direction"],
                    "message_type": info["message_type"],
                    "transfer_bytes": info["transfer_bytes"],
                },
            )

    def note_mapping_wait_start(self, req: Optional[Request], wait_key: str, timestamp: int) -> None:
        req_id = self._request_id(req)
        if req_id is None:
            return
        self._mapping_waits[(req_id, wait_key)] = timestamp

    def note_mapping_wait_end(self, req: Optional[Request], wait_key: str, timestamp: int) -> None:
        req_id = self._request_id(req)
        if req_id is None:
            return
        start = self._mapping_waits.pop((req_id, wait_key), None)
        if start is None:
            return
        rec = self.requests.get(req_id)
        if rec is None:
            return
        self._append_interval(
            rec,
            "intervals",
            "amu_mapping_wait",
            start,
            timestamp,
            {"source": "mapping_wait", "wait_key": wait_key},
        )

    def note_tsu_enqueued(self, tr: Transaction, timestamp: int) -> None:
        self._tsu_enqueue_times.setdefault(id(tr), timestamp)

    def note_tsu_dispatched(self, tr: Transaction, timestamp: int) -> None:
        txn_id = id(tr)
        if txn_id in self._tsu_dispatched:
            return
        self._tsu_dispatched.add(txn_id)
        start = self._tsu_enqueue_times.get(txn_id)
        if start is None or timestamp <= start:
            return
        request_ids, scope = self._request_ids_from_transaction(tr)
        for req_id in request_ids:
            rec = self.requests.get(req_id)
            if rec is None:
                continue
            bucket = "persistence_intervals" if scope == "persistence" else "intervals"
            self._append_interval(
                rec,
                bucket,
                "tsu_queue_wait",
                start,
                timestamp,
                {"source": "tsu", "transaction_type": tr.type.value},
            )

    def note_phy_command_phase(
        self,
        transactions: list[Transaction],
        op_kind: str,
        start_time: int,
        finish_time: int,
        cmd_addr_time: int,
    ) -> None:
        cmd_end = min(finish_time, start_time + cmd_addr_time)
        for tr in transactions:
            self._record_transaction_interval(
                tr,
                "phy_cmd_addr",
                start_time,
                cmd_end,
                {"source": "phy", "transaction_type": tr.type.value, "op_kind": op_kind},
            )
            if finish_time > cmd_end and op_kind in ("write", "search", "compute"):
                self._record_transaction_interval(
                    tr,
                    "phy_data_in",
                    cmd_end,
                    finish_time,
                    {"source": "phy", "transaction_type": tr.type.value, "op_kind": op_kind},
                )

    def note_phy_array_phase(
        self,
        transactions: list[Transaction],
        op_kind: str,
        start_time: int,
        finish_time: int,
    ) -> None:
        for tr in transactions:
            self._record_transaction_interval(
                tr,
                "phy_array_exec",
                start_time,
                finish_time,
                {"source": "phy", "transaction_type": tr.type.value, "op_kind": op_kind},
            )

    def note_phy_data_out_phase(
        self,
        transactions: list[Transaction],
        op_kind: str,
        start_time: int,
        finish_time: int,
    ) -> None:
        for tr in transactions:
            self._record_transaction_interval(
                tr,
                "phy_data_out",
                start_time,
                finish_time,
                {"source": "phy", "transaction_type": tr.type.value, "op_kind": op_kind},
            )

    def note_request_completed(self, req: Request, timestamp: int) -> None:
        rec = self._ensure_request(req)
        rec.host_completion_time = timestamp
        rec.status = req.status
        rec.error_message = req.error_message

    def note_persistence_completed(self, tr: Transaction, timestamp: int) -> None:
        request_ids, scope = self._request_ids_from_transaction(tr)
        if scope != "persistence":
            return
        for req_id in request_ids:
            rec = self.requests.get(req_id)
            if rec is None:
                continue
            rec.persistence_status = "persisted"
            if rec.persistence_completion_time is None or timestamp > rec.persistence_completion_time:
                rec.persistence_completion_time = timestamp

    def export(self) -> dict[str, Any]:
        requests_payload = []
        for rec in sorted(self.requests.values(), key=lambda item: (item.trace_index if item.trace_index is not None else 10**9, item.req_id)):
            total_latency = self._total_latency(rec.req_init_time, rec.host_completion_time)
            host_breakdown = self._summarize_breakdown(rec.intervals, total_latency)
            persistence_total = self._total_latency(rec.req_init_time, rec.persistence_completion_time)
            persistence_breakdown = self._summarize_breakdown(rec.persistence_intervals, persistence_total)
            persistence_status = rec.persistence_status
            if rec.req_type in (RequestType.WRITE.value, RequestType.STATIC_WRITE.value):
                if rec.persistence_completion_time is None and persistence_status != "persisted":
                    persistence_status = "superseded_in_cache"
                    persistence_total = 0
                    persistence_breakdown = _zero_breakdown()
            else:
                persistence_status = "not_applicable"
                persistence_total = 0
                persistence_breakdown = _zero_breakdown()

            requests_payload.append(
                {
                    "req_id": rec.req_id,
                    "trace_index": rec.trace_index,
                    "trace_time": rec.trace_time,
                    "type": rec.req_type,
                    "stream_id": rec.stream_id,
                    "sq_id": rec.sq_id,
                    "lha_start": rec.lha_start,
                    "size": rec.size,
                    "status": rec.status,
                    "error_message": rec.error_message,
                    "scheduled_time": rec.scheduled_time,
                    "req_init_time": rec.req_init_time,
                    "host_completion_time": rec.host_completion_time,
                    "total_latency": total_latency,
                    "host_total_latency": total_latency,
                    "breakdown": host_breakdown,
                    "intervals": rec.intervals,
                    "persistence_status": persistence_status,
                    "persistence_completion_time": rec.persistence_completion_time,
                    "persistence_total_latency": persistence_total,
                    "persistence_breakdown": persistence_breakdown,
                    "persistence_intervals": rec.persistence_intervals,
                }
            )

        return {
            "meta": {
                "trace_path": str(self.trace_path) if self.trace_path is not None else None,
                "trace_name": self.trace_path.name if self.trace_path is not None else None,
                "final_time": int(self.engine.current_time if self.engine is not None else 0),
                "request_count": len(requests_payload),
                "stage_names": list(BASE_STAGE_NAMES),
            },
            "requests": requests_payload,
        }

    def dump_json(self, output_path: str | Path) -> Path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(self.export(), handle, ensure_ascii=False, indent=2)
        return path

    def _ensure_request(self, req: Request) -> RequestLatencyState:
        req_id = self._request_id(req)
        if req_id is None:
            raise ValueError("Request missing report_req_id for latency reporting")
        if req_id not in self.requests:
            self.requests[req_id] = RequestLatencyState(
                req_id=req_id,
                trace_index=req.trace_index,
                trace_time=req.trace_time,
                req_type=req.type.value if hasattr(req.type, "value") else str(req.type),
                lha_start=req.lha_start,
                size=req.size,
                stream_id=req.stream_id,
                sq_id=req.sq_id,
            )
        rec = self.requests[req_id]
        rec.trace_index = req.trace_index
        rec.trace_time = req.trace_time
        rec.stream_id = req.stream_id
        rec.sq_id = req.sq_id
        rec.lha_start = req.lha_start
        rec.size = req.size
        return rec

    def _request_id(self, req: Optional[Request]) -> Optional[str]:
        if req is None:
            return None
        return req.report_req_id

    def _request_ids_from_message(self, message: Any) -> set[str]:
        payload = getattr(message, "payload", None)
        if not isinstance(payload, dict):
            return set()
        req = payload.get("req")
        req_id = self._request_id(req)
        if req_id is not None:
            return {req_id}
        origin_ids = payload.get("origin_request_ids")
        if origin_ids is None:
            return set()
        return {str(req_id) for req_id in origin_ids if req_id}

    def _request_ids_from_transaction(self, tr: Transaction) -> tuple[set[str], str]:
        req_id = self._request_id(tr.source_req)
        if req_id is not None:
            return {req_id}, "host"
        origin_ids = {str(req_id) for req_id in getattr(tr, "report_origin_request_ids", []) if req_id}
        if origin_ids:
            return origin_ids, "persistence"
        return set(), "host"

    def _append_interval(
        self,
        rec: RequestLatencyState,
        bucket_name: str,
        stage: str,
        start: int,
        end: int,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        if end < start:
            start, end = end, start
        if end == start:
            return
        bucket = getattr(rec, bucket_name)
        bucket[stage].append({"start": int(start), "end": int(end), **(metadata or {})})

    def _record_transaction_interval(
        self,
        tr: Transaction,
        stage: str,
        start: int,
        end: int,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        request_ids, scope = self._request_ids_from_transaction(tr)
        if not request_ids:
            return
        bucket_name = "persistence_intervals" if scope == "persistence" else "intervals"
        for req_id in request_ids:
            rec = self.requests.get(req_id)
            if rec is None:
                continue
            self._append_interval(rec, bucket_name, stage, start, end, metadata)

    def _summarize_breakdown(
        self,
        interval_map: dict[str, list[dict[str, Any]]],
        total_latency: int,
    ) -> dict[str, int]:
        summary = _zero_breakdown()
        all_intervals: list[tuple[int, int]] = []
        for stage in BASE_STAGE_NAMES:
            raw_intervals = [(item["start"], item["end"]) for item in interval_map.get(stage, [])]
            summary[stage] = _merged_duration(raw_intervals)
            all_intervals.extend(raw_intervals)
        union_duration = _merged_duration(all_intervals)
        base_sum = sum(summary[stage] for stage in BASE_STAGE_NAMES)
        summary["overlap_latency"] = max(0, base_sum - union_duration)
        summary["untracked_latency"] = max(0, total_latency - union_duration)
        return summary

    def _total_latency(self, start: Optional[int], end: Optional[int]) -> int:
        if start is None or end is None or end < start:
            return 0
        return int(end - start)
