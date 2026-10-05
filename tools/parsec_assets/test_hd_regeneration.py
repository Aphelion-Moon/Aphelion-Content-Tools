import json
from hashlib import sha256
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / 'webapp/frontend/src/assets/parsec'


def test_complete_regeneration_retains_hd_pixel_and_runtime_frames():
	manifest = json.loads((ASSETS / 'source/regeneration-20261004/manifest.json').read_text())
	assert manifest['identityPalette'] == {'anatomicalLeft': '#FBD436', 'anatomicalRight': '#FF3CC8'}
	assert manifest['pixelConverter']['url'] == 'https://portalrabbit.com'
	assert len(manifest['sequences']) == 66
	assert len(manifest['frames']) == 293
	assert len({frame['runtime']['path'] for frame in manifest['frames']}) == 293
	assert len({frame['clip'] for frame in manifest['frames']}) == 60
	for frame in manifest['frames']:
		for kind, expected in [('hd', (512, 512)), ('pixel', (480, 480)), ('runtime', (96, 96))]:
			record = frame[kind]
			path = ROOT / record['path']
			assert sha256(path.read_bytes()).hexdigest() == record['sha256']
			with Image.open(path) as image:
				assert image.mode == 'RGBA' and image.size == expected
				assert image.getchannel('A').getbbox() is not None
				assert max(image.size) <= 512
				if kind == 'pixel':
					native = image.resize((160, 160), Image.Resampling.NEAREST)
					assert native.resize(image.size, Image.Resampling.NEAREST).tobytes() == image.tobytes()
				elif kind == 'runtime':
					colors = set(image.getdata())
					assert all(tuple(iris) in colors for iris in frame['visibleIrisColors']), record['path']


def test_raised_scratch_leg_does_not_leave_a_grounded_hind_paw():
	root = ASSETS / 'prepared/parsec-core/core-idle-scratch'
	counts = []
	for index in range(5):
		with Image.open(root / f'core-idle-scratch__d0__f{index}.png') as image:
			# The hind paw's ground contact lies between the front paw and the tail.
			counts.append(sum(image.getpixel((x,y))[3] > 0 for y in range(83,88) for x in range(42,58)))
	assert counts[0] > 25 and counts[4] > 25
	assert counts[1] == 0 and counts[2] == 0
