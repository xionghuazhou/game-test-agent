"""数据库初始化脚本：建表 + 写入示例知识库（RAG 演示数据）"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal, init_db  # noqa: E402
from app.models.knowledge_base import KnowledgeBase  # noqa: E402

SEED = [
    ("游戏UI常见Bug类型", "1. 文本溢出：输入框未限制长度导致界面错乱\n2. 按钮点击区域偏移：CSS定位问题\n3. 滑块值异常：边界条件未处理（如0值时显示NaN）\n4. 图片加载失败：资源路径错误\n5. 列表滚动异常：虚拟滚动实现问题", "doc", "内部整理", "ui,bug,前端"),
    ("性能测试指标参考", "帧率标准：\n- 60fps：优秀\n- 30fps：可接受\n- <20fps：需要优化\n\n内存标准：\n- <500MB：优秀\n- 500MB-1GB：可接受\n- >1GB：需要优化", "rule", "性能测试规范", "性能,帧率,内存"),
    ("崩溃类Bug处理流程", "1. 复现崩溃步骤\n2. 收集崩溃日志\n3. 分析调用栈\n4. 定位问题代码\n5. 编写修复补丁\n6. 回归测试验证", "rule", "Bug处理SOP", "崩溃,处理流程"),
    ("数值越界类Bug特征", "典型表现：HP/金币/得分等数值出现负数、NaN、Infinity。常见根因：减血公式未做下限截断、除零未保护、整数溢出。判定时注意与正常扣血区分：正常扣血不会低于0。", "bug", "历史Bug库", "logic,数值,越界"),
    ("界面无响应类Bug特征", "典型表现：点击按钮后画面无任何变化，元素仍可点击但无效果。常见根因：事件处理器异常、弹窗遮挡未关闭、网络请求阻塞UI线程。连续点击同一按钮触发无响应概率更高。", "bug", "历史Bug库", "ui,无响应,卡死"),
]


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        if db.query(KnowledgeBase).count() == 0:
            for title, content, cat, src, tags in SEED:
                db.add(KnowledgeBase(title=title, content=content, category=cat, source=src, tags=tags))
            db.commit()
            print(f"✅ 已写入 {len(SEED)} 条示例知识库数据")
        else:
            print("ℹ️ 知识库已有数据，跳过")
        print("✅ 数据库初始化完成")
    finally:
        db.close()


if __name__ == "__main__":
    main()
