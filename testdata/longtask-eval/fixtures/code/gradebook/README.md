# gradebook

学校用的成绩小系统：读成绩 CSV，出成绩单、班级排名、导出表、班级汇总、家长通知、出勤统计。

    python -m gradebook.cli card tests/data/sample.csv 2026001
    python -m gradebook.cli rank tests/data/sample.csv 七年级1班 数学
    python -m gradebook.cli export tests/data/sample.csv out.csv
    python -m gradebook.cli summary tests/data/sample.csv
    python -m gradebook.cli notify tests/data/sample.csv 2026001

测试：python -m unittest discover -s tests -t .
