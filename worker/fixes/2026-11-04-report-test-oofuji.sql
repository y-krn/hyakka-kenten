-- 試作版で試しに送った報告（大富士の1件）を消す。ユーザーの了承済み
DELETE FROM reports WHERE id = 1 AND title = '大富士' AND fk = '職業';
