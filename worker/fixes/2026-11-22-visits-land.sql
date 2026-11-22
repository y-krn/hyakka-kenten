-- 来訪の記録に「どこから入ったか」を足す（top：トップ、today：今日の一戦、pref：県応援の入口、battle：共有された対戦、c：王座戦の記録、hall：殿堂、other：そのほか）
ALTER TABLE visits ADD COLUMN land TEXT;
