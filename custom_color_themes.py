"""
Takes a file from the themes folders and generates one based on a current themes.
"""
from json import loads, dumps
import colorsys
from typing import Callable


def _parse_color(color_str: str) -> tuple:
    color_str = color_str.replace("#", "")
    assert len(color_str) in [3, 6]
    color_bit_length = len(color_str) // 3
    colors = [color_str[i: i + color_bit_length] for i in range(0, len(color_str), color_bit_length)]
    colors = list(map(lambda x: int(x, 16) / (16 ** color_bit_length - 1), colors))
    return tuple(colors)


class ThemeCreator:
    def __init__(self, base_theme: str, central_color_key: str):
        self.theme = dict()
        self.color = None
        self.load_theme(base_theme, central_color_key)

    def load_theme(self, file: str, key: str) -> None:
        with open(file, 'r') as f:
            file_contents = f.read()
            self.theme = loads(file_contents)
            self.color = self.theme[key]

    def _get_hue_rotation(self, color: str) -> float:
        color_rgb = _parse_color(color)
        base_rgb = _parse_color(self.color)

        color_hsv = colorsys.rgb_to_hsv(*color_rgb)
        base_hsv = colorsys.rgb_to_hsv(*base_rgb)

        color_hue = color_hsv[0]
        base_hue = base_hsv[0]

        return color_hue - base_hue

    @staticmethod
    def _apply_hue_rotation(rotation: float, color: str) -> str:
        color_rgb = _parse_color(color)
        color_hsv = colorsys.rgb_to_hsv(*color_rgb)
        rotated_hsv = ((color_hsv[0] + rotation) % 1, color_hsv[1], color_hsv[2])
        rotated_rgb = colorsys.hsv_to_rgb(*rotated_hsv)
        rotated_str = "#" + ''.join(map(lambda x: hex(int(x * 255))[2:].zfill(2), rotated_rgb))
        return rotated_str

    def generate_theme_from_color(self, color: str) -> dict:
        hue_rotation = self._get_hue_rotation(color)

        return {k: self._apply_hue_rotation(hue_rotation, v) for k, v in self.theme.items()}

    def make_theme(self, color_name, color_code):
        theme_base_name: Callable[[str], str] = lambda color: f"./ide_themes/custom_{color}.json"
        with open(theme_base_name(color_name), 'w') as f:
            contents = self.generate_theme_from_color(color_code)
            contents_str = dumps(contents)
            f.write(contents_str)
