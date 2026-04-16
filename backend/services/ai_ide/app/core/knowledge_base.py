import os


class KnowledgeBase:
    """
    负责管理本地量化研发知识库。
    """

    def __init__(self, project_root: str):
        self.project_root = project_root
        self.doc_paths = [
            "docs/Qlib策略模板说明.md",
            "docs/Qlib基础文档.md",
            "GEMINI.md",
        ]
        self.cached_context = ""

    def get_context_summary(self) -> str:
        """
        获取核心文档的摘要信息
        """
        if self.cached_context:
            return self.cached_context

        summary = "### QuantMind Project Standards & API Reference:\n"

        for doc_rel_path in self.doc_paths:
            full_path = os.path.join(self.project_root, doc_rel_path)
            if os.path.exists(full_path):
                try:
                    with open(full_path, encoding="utf-8") as f:
                        content = f.read()
                        summary += f"\n-- From {doc_rel_path} --\n{content[:1500]}\n"
                except Exception as e:
                    summary += f"\n-- Error reading {doc_rel_path}: {str(e)} --\n"

        self.cached_context = summary
        return summary
