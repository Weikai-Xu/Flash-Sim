## MODIFIED Requirements

### Requirement: Trace 瑙ｆ瀽鍣ㄥ繀椤婚獙璇佹敮鎸佺殑鍛戒护鏍煎紡

`parser.py` SHALL 鏀寔浠?JSON 瀛楃涓层€佹枃浠惰矾寰勬垨 Python 鍒楄〃璇诲彇鍛戒护锛屽苟瀵?`read`銆乣write`銆乣static_write`銆乣search` 鍜?`compute` 鐨勫繀濉瓧娈垫墽琛岄獙璇併€傚浜庢惡甯︽暟鎹殑鍛戒护锛宍parser.py` MUST 涓嶅啀瑕佹眰 `data_address` 鎴?`data_size`锛岃€屾槸浠?`size` 浣滀负鍞竴鐨勮姹傞暱搴︽寚绀恒€?

#### Scenario: 瑙ｆ瀽 size-only trace 鏂囦欢

- **WHEN** 璋冪敤 `parse_trace(...)` 璇诲彇涓€涓寘鍚?`write`銆乣static_write`銆乣search` 鎴?`compute` 鍛戒护鐨?JSON trace 鏂囦欢锛屼笖杩欎簺鍛戒护鍙彁渚?`time`銆乣start_lha` 鍜?`size`
- **THEN** 瑙ｆ瀽鍣?MUST 杩斿洖鍛戒护鍒楄〃锛屽苟浠呭鏀寔鐨勫繀濉瓧娈垫墽琛岄獙璇?

#### Scenario: 瑙ｆ瀽 legacy extra fields

- **WHEN** 璋冪敤 `parse_trace(...)` 璇诲彇鐨勫懡浠や腑浠嶇劧鍖呭惈 `data_address` 鎴?`data_size`
- **THEN** 瑙ｆ瀽鍣?MUST 涓嶅皢杩欎簺瀛楁褰撲綔蹇呭～鏉′欢锛屽苟缁х画鍩轰簬鍏朵粬蹇呭～瀛楁瀹屾垚楠岃瘉
