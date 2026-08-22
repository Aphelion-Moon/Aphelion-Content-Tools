from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from webapp.api import create_app


def main(argv: list[str] | None = None) -> int:
	"""Write the OpenAPI schema to a file without starting a server.

	`npm run gen:api` can point at a running server, but that makes type generation depend on one being
	up -- awkward in CI and easy to get wrong locally. This produces the same schema from the app object
	directly, so regenerating types is a two-command sequence with no port involved.
	"""
	parser = argparse.ArgumentParser(description="Dump the API's OpenAPI schema as JSON.")
	parser.add_argument("--output", type=Path, default=Path("webapp/frontend/openapi.json"))
	args = parser.parse_args(argv)

	# The schema is derived entirely from route signatures and Pydantic models, so the roots given here
	# never affect the output -- the app just needs to be constructed.
	app = create_app(Path("."), Path("."))
	schema = app.openapi()

	args.output.parent.mkdir(parents=True, exist_ok=True)
	args.output.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
	print(f"wrote {args.output} ({len(schema['paths'])} paths)", file=sys.stderr)
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
