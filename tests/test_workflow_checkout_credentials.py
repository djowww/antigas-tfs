import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
CHECKOUT_USE = re.compile(r"^(?P<indent>\s*)(?P<dash>-\s*)?uses:\s*(?P<ref>actions/checkout@\S+)\s*$")
SIBLING_STEP = re.compile(r"^(?P<indent>\s*)-\s+")
PERSIST_DISABLED = re.compile(r"^\s+persist-credentials:\s*false\s*$", re.MULTILINE)


class CheckoutCredentialPolicyTests(unittest.TestCase):
    def test_every_checkout_is_sha_pinned_and_does_not_persist_credentials(self):
        checked = 0
        for workflow in sorted(WORKFLOWS.glob("*.yml")):
            lines = workflow.read_text(encoding="utf-8").splitlines()
            for index, line in enumerate(lines):
                match = CHECKOUT_USE.match(line)
                if not match:
                    continue

                checked += 1
                ref = match.group("ref")
                self.assertRegex(ref, r"^actions/checkout@[0-9a-fA-F]{40}$", f"{workflow.name}:{index + 1} must pin checkout to a full commit SHA")

                indent = len(match.group("indent"))
                step_indent = indent if match.group("dash") else indent - 2
                end = len(lines)
                for next_index in range(index + 1, len(lines)):
                    sibling = SIBLING_STEP.match(lines[next_index])
                    if sibling and len(sibling.group("indent")) == step_indent:
                        end = next_index
                        break

                step_text = "\n".join(lines[index:end])
                self.assertRegex(step_text, PERSIST_DISABLED, f"{workflow.name}:{index + 1} must set persist-credentials: false")

        self.assertGreater(checked, 0, "expected at least one actions/checkout step")


if __name__ == "__main__":
    unittest.main()