"""LX1 corpus: 80 students' semester records, far past one context window (#1139).

Seeded, so the eval (upload) and the checker (truth) build the same corpus.
Each record is 20 weekly notes by a 班主任: mostly everyday filler, one note
with the student's standout progress (one of PROGRESS, paraphrased), one with
what the family should help with (one of HOME, paraphrased), and one decoy
that names a *different* progress area as still weak. Labels never appear
verbatim in the text, so the model has to read, not grep.
"""

from __future__ import annotations

import io
import random
import zipfile

SEED = 1139
N_STUDENTS = 80

PROGRESS = ["学习习惯", "课堂参与", "同伴关系", "自我管理", "体育健康", "艺术特长"]
HOME = ["作息与屏幕时间", "亲子阅读", "情绪沟通", "饮食与锻炼", "作业检查与签字"]

PROGRESS_TEXT = {
    "学习习惯": [
        "{n}这学期开始每天放学先列一张清单，写完一项划掉一项，作业再没有拖到第二天早上补。",
        "以前{n}的错题本是空的，现在每次测验后都会把错题抄下来、用红笔写上错因，周末自己再做一遍。",
        "{n}养成了课前预习的习惯，书上用铅笔圈出看不懂的地方，上课就盯着这几处听。",
        "{n}的书桌和书包整理得井井有条，交作业从不翻找，订正也做到了当天清。",
        "{n}现在写作文会先列提纲再动笔，草稿上能看到反复修改的痕迹，不再一口气写完了事。",
    ],
    "课堂参与": [
        "{n}以前上课几乎不出声，这学期每节语文课都会主动举手，有一次还站起来反驳了同学的观点，说得有理有据。",
        "小组讨论时{n}开始当记录员，汇报时声音洪亮，把组里三个人的意见都讲清楚了。",
        "{n}在数学课上提出了一个连老师都没想到的解法，后来每次遇到难题都愿意上黑板试一试。",
        "{n}从坐在角落不抬头，到现在课上追着老师问「为什么」，眼神亮了很多。",
        "公开课上{n}第一个发言，回答完还补充了一句自己的疑问，全班都给了掌声。",
    ],
    "同伴关系": [
        "{n}开学时总一个人吃饭，现在身边有了三四个固定的好朋友，课间常常一起跳绳。",
        "{n}主动帮新转来的同学熟悉校园，还把自己的笔记借给他抄，两人成了同桌好友。",
        "以前{n}和同学一言不合就推搡，这学期学会了先说「我们商量一下」，一次冲突都没有再发生。",
        "{n}在小组里学会了倾听，别人说话不再打断，组员都愿意和{n}一组。",
        "班里有同学被起外号时，{n}站出来制止，并安慰了那位同学，大家都很佩服。",
    ],
    "自我管理": [
        "{n}这学期自己定了起床闹钟，一次都没有迟到，还主动承担了每天开窗通风的任务。",
        "{n}学会了管自己的零花钱，记了一本小账，期末还用攒下的钱给班级图书角买了两本书。",
        "以前{n}的情绪说来就来，现在生气时会先去走廊深呼吸，冷静下来再回教室。",
        "{n}当上了卫生委员，排值日表、检查、记录全都自己安排，从不需要老师提醒。",
        "{n}现在能按自己定的计划分配复习时间，期末前一周把每天要背的内容都贴在了笔袋上。",
    ],
    "体育健康": [
        "{n}跑步原来总是最后一名，坚持每天早上绕操场慢跑，期末八百米及格了，还提高了四十秒。",
        "{n}加入了学校篮球队，训练一次不落，体重和体能都明显改善，脸色也红润了。",
        "以前{n}一上体育课就说肚子疼，现在跳绳一分钟能跳一百五十多下，是班里的前几名。",
        "{n}每天大课间都认真做操，眼保健操也一丝不苟，视力检查结果比上学期好。",
        "运动会上{n}报了跳远，赛前每天放学加练半小时，最后拿了年级第三。",
    ],
    "艺术特长": [
        "{n}的板报设计让整个年级都来参观，配色和排版都是自己琢磨的。",
        "{n}在元旦联欢会上独奏了一首竖笛曲子，练了整整一个月，台下安静得能听见呼吸。",
        "{n}的书法作品被选进了校园文化墙，老师说{n}的字这学期最见功力。",
        "{n}参加了学校合唱团，从不敢开口到担任领唱，音准和台风都进步很大。",
        "{n}用废旧纸箱做的手工模型在科技艺术节上获了奖，创意让评委眼前一亮。",
    ],
}

PROGRESS_WEAK = {
    "学习习惯": "{n}的作业有时还是赶工完成，书写也偶尔潦草，这方面还要继续努力。",
    "课堂参与": "课堂上{n}举手还不算多，希望下学期能更大胆一些。",
    "同伴关系": "{n}和个别同学之间还有些小摩擦，需要学会更多换位思考。",
    "自我管理": "{n}偶尔还会忘带作业本，收拾东西的习惯有待加强。",
    "体育健康": "{n}的体育项目里跳绳还比较弱，平时要多练一练。",
    "艺术特长": "美术课上{n}的作品还比较简单，可以多尝试一些新的画法。",
}

HOME_TEXT = {
    "作息与屏幕时间": [
        "家访时了解到{n}晚上常玩手机到十一点多，第二天上课打哈欠，希望家里能把手机放在客厅，按时睡觉。",
        "{n}周末几乎一整天对着平板看视频，建议家长和孩子约定每天看屏幕的时长，并说到做到。",
        "{n}好几次说前一晚打游戏打到很晚，请家里帮忙把晚上的作息定下来，十点前上床。",
    ],
    "亲子阅读": [
        "{n}很少读课外书，建议家长每天晚饭后陪孩子读二十分钟，再聊一聊书里的故事。",
        "家长会上{n}的妈妈说家里几乎没有书，建议周末带孩子去一次图书馆，一起挑书、一起读。",
        "{n}的阅读量明显不够，希望家长能和孩子一起读完一本整本书，每周交流一次读后感。",
    ],
    "情绪沟通": [
        "{n}遇到不开心的事总憋在心里，建议家长每天抽十分钟专门听孩子说说学校里的事，不急着批评。",
        "{n}最近和爸爸关系有些紧张，建议家里多用商量的口气，孩子发脾气时先接住情绪再讲道理。",
        "{n}考试前会紧张到睡不着，希望家长多鼓励、少比较，让孩子知道尽力就好。",
    ],
    "饮食与锻炼": [
        "{n}早上常常不吃早饭就来上学，第二节课就饿得没精神，请家里保证早餐。",
        "{n}很挑食，午餐几乎不碰蔬菜，建议家长在家也慢慢引导，周末一起去运动一下。",
        "{n}放学后几乎不运动，零食吃得多，希望家长每天陪孩子下楼走走、跳跳绳。",
    ],
    "作业检查与签字": [
        "{n}的家庭作业经常漏写一两项，请家长每晚对照作业记录本检查一遍并签字。",
        "这学期{n}有好几次作业没带或没做，希望家长睡前帮孩子核对一下书包和作业。",
        "{n}的听写本和练习册常常没有家长签字，请家里每天花几分钟看一看孩子的作业。",
    ],
}

PLACES = ["早读", "课间", "午餐时", "大课间", "放学前", "自习课", "劳动课", "班会课", "升旗仪式后", "午休"]
DOINGS = [
    "和同学一起整理了图书角",
    "帮忙把作业本发到每个人手上",
    "在走廊上看了一会儿宣传栏",
    "排队打饭时和前面的同学聊天",
    "安静地把练习册上的题目做完",
    "和小组同学讨论下周的值日安排",
    "把黑板擦得干干净净",
    "帮老师把实验器材搬回了仪器室",
    "参加了年级的广播操比赛彩排",
    "在班级群里看到了下周的活动通知",
    "跟着大家一起背了两首古诗",
    "把上周借的书还给了图书角",
    "听同学讲了一个科学小实验",
    "认真听了学校安全教育讲座",
    "在植物角给绿萝浇了水",
]
REMARKS = [
    "整体状态平稳，没有什么特别的情况。",
    "这周天气转凉，提醒大家添衣，孩子们都很配合。",
    "教室里秩序良好，同学们之间相处融洽。",
    "本周学校组织了消防演练，全班按时有序撤离。",
    "这周课程进度正常，作业量适中。",
    "临近月考，大家的复习节奏都比较紧凑。",
    "周三下了雨，体育课改在室内上，孩子们做了些拉伸。",
    "这周食堂换了新菜单，大部分同学都说好吃。",
    "班里开展了节约用水的主题班会，大家都发了言。",
    "周五下午进行了大扫除，教室焕然一新。",
    "本周有两位同学过生日，班里一起唱了生日歌。",
    "这周学校的读书节开幕了，走廊里挂满了推荐书目。",
]

SURNAMES = "王李张刘陈杨黄赵吴周徐孙马朱胡郭何高林罗郑梁谢宋唐许韩冯邓曹彭曾萧田董潘袁蔡蒋余于杜叶程魏苏吕丁任卢姚沈钟姜崔谭陆范汪廖石金"
GIVEN = "子涵欣怡梓萱浩宇一诺雨桐宇轩可馨思远俊熙若曦雅琪嘉懿晨阳语嫣明哲文博佳琪"


def students() -> list[dict]:
    """Truth rows in 学号 order: id, name, progress, home, file."""
    rng = random.Random(SEED)
    names: set[str] = set()
    rows = []
    for i in range(N_STUDENTS):
        while True:
            name = rng.choice(SURNAMES) + rng.choice(GIVEN) + rng.choice(GIVEN)
            if name not in names:
                names.add(name)
                break
        rows.append(
            {
                "id": f"2026{rng.randrange(100, 999)}{i:02d}",
                "name": name,
                "progress": PROGRESS[i % len(PROGRESS)],
                "home": HOME[(i * 7 + 3) % len(HOME)],
            }
        )
    rng.shuffle(rows)  # file order != 学号 order
    for k, row in enumerate(rows):
        row["file"] = f"{k + 1:02d}_{row['name']}.md"
    return sorted(rows, key=lambda r: r["id"])


def _filler(rng: random.Random, name: str) -> list[str]:
    parts = []
    for _ in range(rng.randint(3, 4)):
        parts.append(f"{rng.choice(PLACES)}，{name}{rng.choice(DOINGS)}。")
    parts += rng.sample(REMARKS, 2)
    return parts


def record(row: dict) -> str:
    rng = random.Random(f"{SEED}-{row['id']}")
    n = row["name"]
    weeks = 20
    slots = rng.sample(range(2, weeks + 1), 3)
    decoy = rng.choice([p for p in PROGRESS if p != row["progress"]])
    special = {
        slots[0]: rng.choice(PROGRESS_TEXT[row["progress"]]).format(n=n),
        slots[1]: rng.choice(HOME_TEXT[row["home"]]).format(n=n),
        slots[2]: PROGRESS_WEAK[decoy].format(n=n),
    }
    lines = [f"# {n} 的成长记录（学号 {row['id']}）", "", "七年级 3 班 · 班主任周记摘录 · 2026 学年第一学期", ""]
    for w in range(1, weeks + 1):
        body = _filler(rng, n) + _filler(rng, n) + _filler(rng, n)
        if w in special:
            body.insert(rng.randrange(1, len(body)), special[w])
        lines.append(f"## 第 {w} 周")
        lines.append("")
        lines.append("".join(body))
        lines.append("")
    return "\n".join(lines)


def corpus_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for row in sorted(students(), key=lambda r: r["file"]):
            info = zipfile.ZipInfo(f"成长记录/{row['file']}", (2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, record(row).encode("utf-8"))
    return buf.getvalue()
