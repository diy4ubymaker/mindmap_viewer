import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mindmap import parsers as P  # noqa: E402

HERE = os.path.dirname(__file__)
SAMPLES = os.path.join(HERE, "..", "samples")


def shape(n):
    return (n.text, [shape(c) for c in n.children])


class ParserTests(unittest.TestCase):
    def test_markdown_sample(self):
        root, _, fmt = P.parse_file(os.path.join(SAMPLES, "amazon_leadership_principles.md"))
        self.assertEqual(fmt, "markdown")
        self.assertEqual(root.text, "Amazon's 16 Leadership Principles Clusters")
        self.assertEqual(len(root.children), 5)
        own = root.children[2]
        self.assertEqual([c.text for c in own.children],
                         ["Ownership", "Frugality", "Success and Scale Bring Broad Responsibility"])
        self.assertTrue(own.children[1].collapsed)
        self.assertFalse(own.children[0].collapsed)
        self.assertEqual(root.max_depth(), 3)

    def test_indented_text(self):
        t = "Root\n\tA\n\t\tA1\n\t\tA2\n\tB\n\t  B1\n"
        r = P.parse_text(t, "text")
        self.assertEqual(shape(r), ("Root", [("A", [("A1", []), ("A2", [])]), ("B", [("B1", [])])]))

    def test_bullets_without_heading_make_root(self):
        r = P.parse_text("- A\n  - a\n- B\n", "markdown", title="T")
        self.assertEqual(shape(r), ("T", [("A", [("a", [])]), ("B", [])]))

    def test_inline_md(self):
        r = P.parse_text("# **Bold** root\n- [Link](https://x.y) `code`\n")
        self.assertEqual(r.text, "Bold root")
        self.assertEqual(r.children[0].text, "Link code")
        self.assertEqual(r.children[0].link, "https://x.y")

    def test_mermaid(self):
        t = """mindmap
  root((Main topic))
    Origins
      Long history
      ::icon(fa fa-book)
      Popularisation
        buzan[Tony Buzan]
    Tools
      id1(Pen and paper)
"""
        r = P.parse_text(t)
        self.assertEqual(r.text, "Main topic")
        self.assertEqual([c.text for c in r.children], ["Origins", "Tools"])
        self.assertEqual(r.children[0].children[1].children[0].text, "Tony Buzan")
        self.assertEqual(r.children[1].children[0].text, "Pen and paper")

    def test_opml_roundtrip(self):
        r = P.parse_text(P.to_opml(P.parse_text("# R\n- a\n  - b\n- c")))
        self.assertEqual(shape(r), ("R", [("a", [("b", [])]), ("c", [])]))

    def test_json_variants(self):
        self.assertEqual(shape(P.parse_text('{"name":"R","children":[{"name":"a"}]}')), ("R", [("a", [])]))
        self.assertEqual(shape(P.parse_text('{"R": {"a": ["x", "y"], "b": null}}')),
                         ("R", [("a", [("x", []), ("y", [])]), ("b", [])]))
        jsm = '{"meta":{},"format":"node_tree","data":{"id":"root","topic":"R","children":[{"id":"1","topic":"a"}]}}'
        self.assertEqual(shape(P.parse_text(jsm)), ("R", [("a", [])]))

    def test_freemind_roundtrip(self):
        src = P.parse_text("# R\n- a <!-- fold -->\n  - b\n- c")
        r = P.parse_text(P.to_freemind(src))
        self.assertEqual(shape(r), shape(src))
        self.assertTrue(r.children[0].collapsed)

    def test_markdown_roundtrip_all_writers(self):
        root, _, _ = P.parse_file(os.path.join(SAMPLES, "amazon_leadership_principles.md"))
        for name, (ext, fn) in P.WRITERS.items():
            back = P.parse_text(fn(root))
            self.assertEqual(shape(back), shape(root), name)

    def test_samples_all_parse(self):
        for f in os.listdir(SAMPLES):
            if os.path.splitext(f)[1].lower() in P.IMAGE_EXTS:
                continue
            root, _, _ = P.parse_file(os.path.join(SAMPLES, f))
            self.assertGreater(root.count(), 3, f)

    def test_code_fence_and_notes(self):
        t = "# R\n```\n- not a node\n```\n- a\n  continued note\n- b\n"
        r = P.parse_text(t)
        self.assertEqual([c.text for c in r.children], ["a", "b"])
        self.assertEqual(r.children[0].note, "continued note")


if __name__ == "__main__":
    unittest.main()
