# -*- coding: utf-8 -*-
"""fetch_figures 离线单元测试：图号解析、出版社判定、原图 URL 改写、分辨率判定（不联网）。"""
import importlib.util
import io
import os
import pathlib
import unittest

MODULE = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "fetch_figures.py"
spec = importlib.util.spec_from_file_location("fetch_figures", MODULE)
ff = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ff)


class FigureNoTest(unittest.TestCase):
    def test_from_alt_text(self):
        self.assertEqual(ff.figure_no({"alt": "Figure 3. Refer to caption", "src": ""}), 3)

    def test_from_wiley_filename(self):
        img = {"alt": "Details are in the caption", "src": "https://x/cms/asset/u/adma201806133-fig-0002-m.jpg"}
        self.assertEqual(ff.figure_no(img), 2)

    def test_from_elsevier_filename(self):
        img = {"alt": "", "src": "https://ars.els-cdn.com/content/image/1-s2.0-S007-gr12.jpg"}
        self.assertEqual(ff.figure_no(img), 12)

    def test_from_acs_asset_index(self):
        img = {"alt": "", "src": "https://acs.silverchair-cdn.com/acs/.../m_cr3001109_0021.png"}
        self.assertEqual(ff.figure_no(img), 21)

    def test_unparseable_returns_none(self):
        self.assertIsNone(ff.figure_no({"alt": "", "src": "https://x/logo.png"}))


class PublisherTest(unittest.TestCase):
    def test_classification(self):
        self.assertEqual(ff.publisher_of("https://acs.silverchair-cdn.com/a.png"), "acs")
        self.assertEqual(ff.publisher_of("https://onlinelibrary.wiley.com/cms/asset/x.jpg"), "wiley")
        self.assertEqual(ff.publisher_of("https://ars.els-cdn.com/content/image/gr1.jpg"), "elsevier")
        self.assertEqual(ff.publisher_of("https://rscj.silverchair-cdn.com/x.gif"), "rsc")
        self.assertEqual(ff.publisher_of("https://example.org/a.png"), "other")

    def test_acs_medium_stripped_for_full_res(self):
        src = "https://acs.silverchair-cdn.com/acs/content_public/journal/chreay/112/10/x/3/m_cr3001109_0021.png?Expires=1"
        url, note = ff.best_url(src)
        self.assertIn("/3/cr3001109_0021.png", url)
        self.assertNotIn("/m_", url)
        self.assertEqual(note, "已切换为原图")

    def test_non_acs_url_untouched(self):
        src = "https://ars.els-cdn.com/content/image/1-s2.0-S007-gr1.jpg"
        self.assertEqual(ff.best_url(src), (src, ""))

    def test_junk_filter(self):
        self.assertTrue(ff.JUNK.search("https://x/journal-cover.jpg"))
        self.assertTrue(ff.JUNK.search("alt=spinner"))
        self.assertFalse(ff.JUNK.search("adma201806133-fig-0002-m.jpg"))


class ResolutionTest(unittest.TestCase):
    """300 dpi 下可印宽度 = px / 300 * 2.54 cm；8 cm 是默认合格线。"""

    def test_widths(self):
        cases = {2100: 17.8, 1000: 8.5, 472: 4.0}
        for px, cm in cases.items():
            self.assertAlmostEqual(round(px / 300 * 2.54, 1), cm, places=1)

    def test_threshold_judgement(self):
        self.assertTrue(1000 / 300 * 2.54 >= 8.0)   # Wiley 1000 px 刚好合格
        self.assertFalse(472 / 300 * 2.54 >= 8.0)   # Elsevier 小图不合格


class CaptionTest(unittest.TestCase):
    def test_strips_viewer_noise(self):
        s = "Figure 1\nOpen in figure viewer\nPowerPoint\nChemical structure of PEDOT:PSS"
        self.assertEqual(ff.clean_caption(s), "Chemical structure of PEDOT:PSS")

    def test_strips_copyright_tail(self):
        s = ("Enhancing stretchability by blending with ionic liquids. "
             "Adapted with permission from CC BY-NC")
        self.assertEqual(ff.clean_caption(s),
                         "Enhancing stretchability by blending with ionic liquids")

    def test_empty(self):
        self.assertEqual(ff.clean_caption(""), "")
        self.assertEqual(ff.clean_caption(None), "")


class WriteBackTest(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.dir = tempfile.mkdtemp(prefix="pf-wb-")
        os.makedirs(os.path.join(self.dir, "共混"))
        self.md = os.path.join(self.dir, "共混", "x.md")
        body = ("---\ntitle: t\ndoi: 10.1002/adma.201806133\n---\n\n"
                "# t\n\n正文\n\n## 参考文献\n\n[1] a.\n")
        io.open(self.md, "w", encoding="utf-8").write(body)
        self.recs = [{"fig": 1, "file": os.path.join("figs", "src", "k_fig01.jpg"),
                      "alt": "chemical structure", "px": "1000x373"}]

    def test_find_md_by_doi(self):
        self.assertEqual(ff.find_md_for_doi(self.dir, "10.1002/adma.201806133"), self.md)

    def test_insert_before_references(self):
        out = ff.write_back("10.1002/adma.201806133", self.dir, self.recs)
        self.assertEqual(out, self.md)
        text = io.open(self.md, encoding="utf-8").read()
        self.assertIn("## 插图", text)
        self.assertIn("![图 1：chemical structure]", text)
        self.assertLess(text.index("## 插图"), text.index("## 参考文献"))

    def test_idempotent(self):
        ff.write_back("10.1002/adma.201806133", self.dir, self.recs)
        ff.write_back("10.1002/adma.201806133", self.dir, self.recs)
        text = io.open(self.md, encoding="utf-8").read()
        self.assertEqual(text.count("## 插图"), 1)

    def test_unknown_doi_returns_empty(self):
        self.assertEqual(ff.write_back("10.9999/none", self.dir, self.recs), "")


if __name__ == "__main__":
    unittest.main()
