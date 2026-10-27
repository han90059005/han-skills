# -*- coding: utf-8 -*-
"""paper-finder 离线单元测试：去重、来源类型与元数据清洗（不联网）。"""
import importlib.util
import pathlib
import unittest

MODULE = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "paper_finder.py"
spec = importlib.util.spec_from_file_location("paper_finder", MODULE)
pf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pf)


def rec(title, doi="", typ="article"):
    return {"title": title, "doi": doi, "type": typ}


class DedupeTest(unittest.TestCase):
    def test_same_doi_case_insensitive(self):
        items = [rec("A", "10.1/ABC"), rec("A", "10.1/abc")]
        unique, dropped = pf.dedupe_results(items)
        self.assertEqual(len(unique), 1)
        self.assertEqual(dropped, 1)

    def test_title_only_merges_with_doi_record(self):
        items = [rec("Same Study", "10.1/x"), rec("Same  Study!", "")]
        unique, dropped = pf.dedupe_results(items)
        self.assertEqual(len(unique), 1)
        self.assertEqual(dropped, 1)

    def test_same_title_different_doi_kept(self):
        items = [rec("Editorial", "10.1/a"), rec("Editorial", "10.1/b")]
        unique, dropped = pf.dedupe_results(items)
        self.assertEqual(len(unique), 2)
        self.assertEqual(dropped, 0)

    def test_type_label(self):
        self.assertEqual(pf.type_label("review"), "综述")
        self.assertEqual(pf.type_label("journal-article"), "期刊论文")
        self.assertEqual(pf.type_label("posted-content"), "预印本")
        self.assertEqual(pf.type_label(""), "未知")


class CleanTextTest(unittest.TestCase):
    def test_strips_tags_and_entities(self):
        self.assertEqual(
            pf.clean_text("Flexible Ag<sub>2</sub>Se &amp; film"),
            "Flexible Ag2Se & film",
        )
        self.assertEqual(pf.clean_text(None), "")
        self.assertEqual(pf.clean_text("  title  "), "title")


if __name__ == "__main__":
    unittest.main()
