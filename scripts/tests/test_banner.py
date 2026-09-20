import io
import unittest
from contextlib import redirect_stdout

from app.src.Utils.banner import BANNER, print_banner


class BannerTests(unittest.TestCase):
    def test_no_line_ends_with_backslash(self):
        # 字元画每行末尾的空格是自带的补白。删掉之后有两行会以反斜线结尾，
        # raw string 里那会把换行一起吃掉，整幅画塌成一行。
        offenders = [
            index
            for index, line in enumerate(BANNER.split("\n"), start=1)
            if line.endswith("\\")
        ]
        self.assertEqual(offenders, [], f"第 {offenders} 行以反斜线结尾，行尾空格被删了")

    def test_three_blocks_of_nine_lines(self):
        blocks = [
            block.split("\n")
            for block in BANNER.strip("\n").split("\n\n")
        ]
        self.assertEqual(len(blocks), 3, "横幅应该是 MITAHILL / BETTER / VIDEO 三块")
        for block in blocks:
            self.assertEqual(len(block), 9)

    def test_print_banner_writes_plain_stdout(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            print_banner()
        output = buffer.getvalue()
        self.assertIn("$$$$$$/", output)
        # 不走 logging，所以不该带级别和 logger 名前缀
        self.assertNotIn("[INFO]", output)
        self.assertNotIn("[MAIN]", output)


if __name__ == "__main__":
    unittest.main()
