# 班费账本（七年级 3 班）

班主任自己用的小工具：记班费的收和支，给家长出账。

- `classfund/money.py` 金额格式化 / 解析
- `classfund/ledger.py` 账本
- `classfund/roster.py` 花名册
- `classfund/api_v1.py` 家长小程序接口（已上线）
- `data/` 花名册和 9–10 月的流水样例

跑测试：`python -m unittest discover -s tests`
