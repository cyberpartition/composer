"""Run Composer with: python -m composer"""

from __future__ import annotations


def _main() -> int:
    try:
        from composer.app import main
    except ImportError as exc:
        print("Composer is missing a dependency.")
        print(exc)
        print("From this folder, run:  pip install -r requirements.txt")
        return 1
    return main()


if __name__ == "__main__":
    raise SystemExit(_main())
