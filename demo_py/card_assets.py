"""card_assets.py - Shared card image loader & renderer for CPE Escape (Rounds 1 to 5)."""
import os
import pygame

CAREER_KEYS = ("air", "earth", "water")   # 0: AIR, 1: EARTH, 2: WATER
EXTS = (".png", ".jpg", ".jpeg", ".webp")

R1_BACK_NAMES = {
    0: ("air_back",),
    1: ("earth_back",),
    2: ("water_back",),
}

R1_FRONT_NAMES = {
    0: ("air_r1",),
    1: ("earth_r1",),
    2: ("water_r1",),
}

R2_TO_5_BACK_NAMES = {
    0: (("air_card1",), ("air_card2",), ("air_card3",)),
    1: (("eartg_card1", "earth_card1"), ("earth_card2",), ("earth_card3",)),
    2: (("water_card1",), ("water_card2",), ("water_card3",)),
}


class CardAssets:
    def __init__(self, asset_dir=None, card_size=(170, 170)):  # กำหนดขนาดมาตรฐานให้การ์ดเท่ากันทุกใบ
        here = os.path.dirname(os.path.abspath(__file__))
        self.search_dirs = []
        if asset_dir:
            self.search_dirs.append(asset_dir)
        self.search_dirs.extend([
            os.path.join(os.path.dirname(here), "assets"),
            os.path.join(here, "assets"),
            os.path.join(os.getcwd(), "assets"),
            here,
            os.getcwd(),
        ])
        self.card_size = card_size
        self.cache = {}

    def _find_file(self, stem):
        for d in self.search_dirs:
            if not d or not os.path.isdir(d):
                continue
            for ext in EXTS:
                path = os.path.join(d, stem + ext)
                if os.path.isfile(path):
                    return path
        return None

    def _load(self, candidates, size=None):
        target_size = size if size is not None else self.card_size
        if isinstance(candidates, list):
            candidates = tuple(candidates)
            
        key = (candidates, target_size)
        if key in self.cache:
            return self.cache[key]

        img = None
        for stem in candidates:
            path = self._find_file(stem)
            if path:
                try:
                    raw = pygame.image.load(path).convert_alpha()
                    # บังคับปรับขนาดให้เท่ากับ slot ของการ์ดเสมอ เพื่อให้หน้าและหลังขนาดเท่ากันเป๊ะ
                    img = pygame.transform.smoothscale(raw, target_size) if target_size else raw
                    break
                except (pygame.error, ValueError):
                    img = None
        self.cache[key] = img
        return img

    def get_image(self, round_num, career_idx, pos, revealed, slot_idx=None, size=None, item_name=None):
        if career_idx is None or not (0 <= career_idx < len(CAREER_KEYS)):
            career_idx = 0
            
        cat = CAREER_KEYS[career_idx]
        
        if round_num == 1:
            idx = slot_idx if slot_idx is not None else pos
            return self.get_r1_front(idx, size) if revealed else self.get_r1_back(idx, size)
        
        # รอบ 2 ถึง 5
        candidates = []
        if revealed and item_name:
            item_lower = item_name.lower()
            candidates.append(f"{cat}_{item_lower}")
            candidates.append(item_lower)
        
        if career_idx in R2_TO_5_BACK_NAMES and 0 <= pos <= 2:
            for name in R2_TO_5_BACK_NAMES[career_idx][pos]:
                candidates.append(name)

        return self._load(candidates, size)

    def get_r1_back(self, slot_career_idx, size=None):
        names = R1_BACK_NAMES.get(slot_career_idx, ())
        return self._load(names, size)

    def get_r1_front(self, slot_career_idx, size=None):
        names = R1_FRONT_NAMES.get(slot_career_idx, ())
        return self._load(names, size)

    def draw_card(self, surface, slot_rect, round_num, career_idx, pos, revealed,
                  slot_idx=None, fallback_color=(80, 85, 100), item_name=None):
        img = self.get_image(round_num, career_idx, pos, revealed, slot_idx=slot_idx, item_name=item_name)
        if img is not None:
            drawn_rect = img.get_rect(center=slot_rect.center)
            surface.blit(img, drawn_rect.topleft)
            return True, drawn_rect
        pygame.draw.rect(surface, fallback_color, slot_rect, border_radius=10)
        return False, slot_rect