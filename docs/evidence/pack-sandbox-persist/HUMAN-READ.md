# T-SANDBOX-PERSIST 人读

```text
卡: #553 / #556
CLAIM-WB-DEGREE-WEB: NO
```

杀会话前后必须是两张不同的图。Writer 再开必须能读到写入时的那句字。用户 B 必须是另一张（空列表 / 403），禁止复用 T1。

| 帧 | 含义 |
|----|------|
| t1-before-destroy.png | 写入 unique.docx 后、destroy 前的文件树 |
| t1-after-destroy.png | 新会话文件树仍见该名 |
| t2-writer.png | 再开 Writer，正文是盘上那句已知字 |
| t3-acl.png | 用户 B 空列表 + 403 |
| HASHES.txt | 四帧 sha256，必须两两不同 |

公网帧进 `live/`，hash 不得等于本目录夹具。
