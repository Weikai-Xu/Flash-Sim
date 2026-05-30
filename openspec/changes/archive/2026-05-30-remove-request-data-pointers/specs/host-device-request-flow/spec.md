## MODIFIED Requirements

### Requirement: 鍐欏叆绫昏姹傚繀椤诲厛鍚?Host 鑾峰彇鏁版嵁骞跺啓鍏ユ帶鍒跺櫒缂撳瓨

瀵?`WRITE`銆乣SEARCH`銆乣COMPUTE` 鍜?`STATIC_WRITE`锛宍HIL` SHALL 鍏堝悜 `Host` 璇锋眰鏁版嵁杞借嵎锛涗絾 `Host` MUST 浠呭熀浜?`Request.size` 鐢熸垚绛夐暱鍗犱綅鏁版嵁锛屼笉鍐嶄緷璧?`Request.data_address` 鎴?`Request.data_size`銆傚 `WRITE` 鍜?`STATIC_WRITE`锛屾暟鎹埌杈惧悗 MUST 琚垏鐗囧啓鍏ユ帶鍒跺櫒 cache锛屽苟浠モ€滄帶鍒跺櫒宸叉帴鏀垛€濅负璇箟鍚?Host 杩斿洖璇锋眰瀹屾垚銆?

#### Scenario: Write 鏁版嵁鍒拌揪鎺у埗鍣?

- **WHEN** `HIL` 鏀跺埌 `WRITE_DATA` 鎴?`STATIC_WRITE_DATA`
- **THEN** `Host` MUST 杩斿洖闀垮害涓?`Request.size` 鐨勫崰浣嶆暟鎹垪琛紝`HIL` MUST 鎶婃暟鎹寜浜嬪姟绮掑害鍒囩墖銆佸啓鍏?cache锛屽苟绔嬪嵆鍙戦€?`REQ_COMP` 缁?Host锛岃€屼笉瑕佹眰绛夊緟 NAND program 瀹屾垚
