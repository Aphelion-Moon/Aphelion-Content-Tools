from __future__ import annotations


def expression_fragment(text: str) -> None:
	"""Reject declaration boundaries; semantic parsing remains the analyzer's job.

	Multiline expressions must stay inside delimiters or quoted text. Ambiguous
	continuation syntax is deliberately source-inspection-only instead of authorizing
	an initializer patch that could escape into another declaration.
	"""
	stack: list[str] = []
	quote: str | None = None
	comment: str | None = None
	ended = False
	seen = False
	index = 0
	while index < len(text):
		char, pair = text[index], text[index:index + 2]
		if comment == 'line':
			if char == '\n':
				comment = None
				ended = seen and not stack
		elif comment == 'block':
			if char == '\n' and seen and not stack:
				ended = True
			if pair == '*/':
				comment = None
				index += 1
		elif quote:
			if char == '\\':
				index += 1
			elif char == quote:
				quote = None
		elif pair in ('//', '/*'):
			comment = 'line' if pair == '//' else 'block'
			index += 1
		elif char.isspace():
			if char == '\n' and seen and not stack:
				ended = True
		else:
			if ended or char == ';':
				raise ValueError('A field must contain one expression. Wrap multiline expressions in parentheses; additional declarations are forbidden.')
			seen = True
			if char in ('"', "'"):
				quote = char
			elif char in '([{':
				stack.append(char)
			elif char in ')]}' and (not stack or stack.pop() != {')': '(', ']': '[', '}': '{'}[char]):
				raise ValueError('Unbalanced expression delimiters.')
		index += 1
	if not seen or stack or quote or comment == 'block':
		raise ValueError('Incomplete expression; preserve it in source until it can be parsed safely.')


def procedure_fragment(text: str, type_path: str, name: str) -> None:
	lines = text.splitlines()
	if not lines or not lines[0].startswith((f'{type_path}/{name}(', f'{type_path}/proc/{name}(')):
		raise ValueError(f'Procedure {name} requires its complete header on {type_path}.')
	# The initial header may span several indented lines. A zero-column closing
	# parenthesis is permitted, but another zero-column declaration is never part
	# of this procedure. Helper procedures get their own named draft entries.
	header = True
	for index, line in enumerate(lines):
		stripped = line.strip()
		if index == 0:
			header = ')' not in line
			continue
		if stripped and not line[0].isspace() and not stripped.startswith('//') and not (header and stripped == ')'):
			raise ValueError('A procedure fragment cannot introduce another top-level declaration.')
		if header and ')' in line:
			header = False
