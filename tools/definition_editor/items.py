from __future__ import annotations

import hashlib
from pathlib import Path

from tools.dmi import Dmi
from tools.lore_editor.icon_preview import _get_icon_state, _resolve_icon_path, render_icon_preview

from .models import Definition, DefinitionConstant, ItemPreview


def item_preview(root: Path, definition: Definition, catalog_id: str, *, slot: str | None = None, constants: list[DefinitionConstant] | None = None) -> ItemPreview:
	fields = {field.name: field for field in definition.fields}
	icon, state = fields.get('icon'), fields.get('icon_state')
	if not icon or not state or not icon.value_known or not state.value_known or not isinstance(icon.value, str) or not isinstance(state.value, str):
		raise ValueError('This item has no statically resolved icon and icon state. Use native preview.')
	path = _resolve_icon_path(root, icon.value)
	digest = hashlib.sha256(path.read_bytes()).hexdigest()
	dmi = Dmi.from_file(path)
	try:
		icon_state = _get_icon_state(dmi, state.value)
	except KeyError as exc:
		raise ValueError('The selected item icon state is missing.') from exc
	diagnostics = ['Worn appearance, species fit, equip hooks, and slot behavior require native preview.']
	if slot:
		names = {'uniform': 'ICLOTHING', 'suit': 'OCLOTHING', 'head': 'HEAD', 'mask': 'MASK', 'neck': 'NECK', 'shoes': 'FEET', 'gloves': 'GLOVES', 'ears': 'EARS', 'glasses': 'EYES', 'belt': 'BELT', 'back': 'BACK', 'id': 'ID'}
		flag_name = 'ITEM_SLOT_' + names.get(slot, '')
		flag = next((item.value for item in constants or [] if item.name == flag_name and item.value_known), None)
		slot_flags = fields.get('slot_flags')
		if isinstance(flag, int) and slot_flags and slot_flags.value_known and isinstance(slot_flags.value, int):
			diagnostics.insert(0, f'{slot}: item slot flags permit this slot.' if slot_flags.value & flag else f'Incompatible slot flags: this item does not permit {slot}. Custom equip behavior still requires native verification.')
		else:
			diagnostics.append(f'{slot}: compatibility is unresolved statically; use native preview.')
	return ItemPreview(type_path=definition.type_path, catalog_id=catalog_id, file=icon.value, state=state.value, asset_sha256=digest, directions=[2, 1, 4, 8, 6, 10, 5, 9][:icon_state.dirs], frames=icon_state.framecount, diagnostics=diagnostics)


def item_image(root: Path, metadata: ItemPreview, asset_hash: str, direction: int, frame: int) -> bytes:
	if metadata.asset_sha256 != asset_hash:
		raise ValueError('Item sprite changed; refresh its preview metadata.')
	return render_icon_preview(root, metadata.file, metadata.state, direction=direction, frame=frame)
