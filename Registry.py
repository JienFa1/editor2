# -*- coding: utf-8 -*-
"""
registry.py — sử dụng 'compose' theo config.py (phiên bản có chú thích từng dòng)

Yêu cầu (theo config hiện tại):
- multi_label_strategy = "union"   → hợp các edit_prompt của mọi nhãn
- deduplicate = True               → loại trùng theo nguyên tắc "gặp trước giữ trước"
- ordering = "by_global_order"     → sắp xếp theo compose.global_prompt_order (phải bao phủ mọi ID)
- base_system_prompt lấy từ compose.base_system_prompt
- Trả về sẵn 'system_prompt' để module khác chỉ cần truyền user = đoạn văn

API công khai:
- PromptRegistry.from_dict(dict) -> PromptRegistry
- PromptRegistry.from_json(path) -> PromptRegistry
- base_system_prompt() -> str
- combine_edit_prompts(label_keys: List[str]) -> (selected_labels: List[str], edit_prompts: List[EditPrompt])
- build_system_prompt(label_keys: List[str]) -> (system_prompt: str, selected_labels: List[str], edit_prompt_ids: List[str])
"""

import json  # nạp file JSON nếu cần from_json
from dataclasses import dataclass  # tạo kiểu dữ liệu nhẹ cho EditPrompt
from typing import Dict, List, Tuple, Any  # gợi ý kiểu cho hàm/lớp


# -----------------------------
# Kiểu dữ liệu quy tắc biên tập
# -----------------------------
@dataclass
class EditPrompt:
    id: str   # mã định danh quy tắc, ví dụ "EP_LEAD_TBMV"
    text: str # nội dung yêu cầu biên tập, hiển thị dạng bullet trong system prompt


# -----------------------------
# Lớp tra cứu nhãn ↔ quy tắc
# -----------------------------
class PromptRegistry:
    def __init__(
        self,
        labels: List[Dict[str, Any]],        # danh mục nhãn (metadata cơ bản)
        edit_prompts: List[Dict[str, Any]],  # danh sách quy tắc biên tập
        mapping: List[Dict[str, Any]],       # ánh xạ N-N: label_key -> [edit_prompt_id]
        compose: Dict[str, Any],             # cấu hình compose (union + dedupe + order + base_system)
    ):
        # Lưu toàn bộ compose để dùng ở các bước kết hợp/sắp xếp/sinh system
        self.compose: Dict[str, Any] = compose or {}

        # Chuẩn hoá edit_prompts thành dict: id -> EditPrompt
        self._edit_prompts_by_id: Dict[str, EditPrompt] = {}  # khởi tạo kho quy tắc theo ID
        for ep in (edit_prompts or []):                       # duyệt từng mục cấu hình quy tắc
            ep_id = str(ep.get("id", "")).strip()             # lấy trường id và làm sạch khoảng trắng
            ep_text = str(ep.get("text", "")).strip()         # lấy trường text và làm sạch
            if ep_id and ep_text:                             # chỉ nhận mục có đủ id và text
                self._edit_prompts_by_id[ep_id] = EditPrompt( # lưu vào dict dưới dạng EditPrompt
                    id=ep_id,
                    text=ep_text
                )

        # Chuẩn hoá mapping: label_key -> list[edit_prompt_id] (chỉ giữ ID tồn tại)
        self._map_label_to_epids: Dict[str, List[str]] = {}   # khởi tạo bảng ánh xạ nhãn → danh sách EP ID
        for row in (mapping or []):                           # duyệt từng dòng map
            label_key = str(row.get("label_key", "")).strip() # lấy key của nhãn
            ep_ids_raw = row.get("edit_prompt_ids", [])       # lấy danh sách id quy tắc từ cấu hình
            # Lọc chỉ giữ những id có thực trong _edit_prompts_by_id
            ep_ids = [eid for eid in ep_ids_raw if eid in self._edit_prompts_by_id]
            if label_key and ep_ids:                          # nếu nhãn có tên và có ít nhất 1 quy tắc hợp lệ
                self._map_label_to_epids[label_key] = ep_ids  # lưu ánh xạ nhãn → danh sách quy tắc

        # Tạo bảng xếp hạng toàn cục theo compose.global_prompt_order
        gpo_list = list(self.compose.get("global_prompt_order") or [])  # lấy danh sách ưu tiên toàn cục
        self._global_rank: Dict[str, int] = {eid: i for i, eid in enumerate(gpo_list)}  # map id → thứ hạng

    # -----------------------------
    # Factory helpers
    # -----------------------------
    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "PromptRegistry":
        # Hàm dựng nhanh từ dict cấu hình (thường là REGISTRY_DICT trong config.py)
        return PromptRegistry(
            labels=d.get("labels", []),             # truyền danh sách labels
            edit_prompts=d.get("edit_prompts", []), # truyền danh sách edit_prompts
            mapping=d.get("map", []),               # truyền danh sách map
            compose=d.get("compose", {}),           # truyền compose (union + dedupe + order + base_system)
        )

    @staticmethod
    def from_json(path: str) -> "PromptRegistry":
        # Hàm dựng từ file JSON ngoài (nếu bạn tách cấu hình ra file .json)
        with open(path, "r", encoding="utf-8") as f:  # mở file cấu hình dạng JSON
            data = json.load(f)                       # nạp nội dung JSON thành dict
        return PromptRegistry.from_dict(data)         # gọi lại from_dict để khởi tạo

    # -----------------------------
    # Truy xuất system chung
    # -----------------------------
    def base_system_prompt(self) -> str:
        # Trả về compose.base_system_prompt; nếu thiếu thì dùng chuỗi mặc định an toàn
        return str(
            self.compose.get("base_system_prompt")
            or "Bạn là biên tập viên tin tức mục vụ. Chỉ trả về nội dung đã chỉnh sửa theo yêu cầu. "
               "Giữ trung thực dữ kiện; không thêm thông tin mới; tôn trọng bối cảnh mục vụ."
        )

    # -----------------------------
    # Nội bộ: lọc nhãn hợp lệ theo map
    # -----------------------------
    def _valid_input_labels(self, label_keys: List[str]) -> List[str]:
        # Giữ nguyên thứ tự input; chỉ nhận nhãn có xuất hiện trong bảng map
        return [k for k in (label_keys or []) if k in self._map_label_to_epids]

    # -----------------------------
    # Nội bộ: hợp + khử trùng lặp theo thứ tự input
    # -----------------------------
    def _union_eids_by_input_order(self, valid_labels: List[str]) -> List[str]:
        seen = set()       # tập hợp để kiểm tra trùng lặp nhanh
        out: List[str] = []# danh sách kết quả eids theo thứ tự đã gặp
        for lbl in valid_labels:                                        # duyệt từng nhãn theo thứ tự input
            for eid in self._map_label_to_epids.get(lbl, []):           # duyệt từng edit_prompt_id của nhãn đó
                if eid not in seen:                                     # nếu id chưa xuất hiện trước đó
                    seen.add(eid)                                       # đánh dấu đã thấy
                    out.append(eid)                                     # thêm vào kết quả
        return out                                                      # trả danh sách eids sau union+dedupe

    # -----------------------------
    # Nội bộ: sắp xếp theo global_prompt_order (bắt buộc đủ)
    # -----------------------------
    def _order_by_global(self, eids: List[str]) -> List[str]:
        # Lấy bảng thứ hạng toàn cục đã khởi tạo trong __init__
        rank = self._global_rank
        # Nếu compose không có global_prompt_order → báo lỗi cấu hình để bạn bổ sung
        if not rank:
            raise ValueError("compose.global_prompt_order is missing or empty in config.")

        # Kiểm tra mọi eids đều có mặt trong global_prompt_order; nếu thiếu → báo lỗi rõ ràng
        missing = [eid for eid in eids if eid not in rank]
        if missing:
            raise ValueError(f"compose.global_prompt_order is missing IDs: {missing}")

        # Sắp xếp eids theo thứ hạng rank[eid] (nhỏ → đứng trước)
        return sorted(eids, key=lambda x: rank[x])

    # -----------------------------
    # API: kết hợp quy tắc theo danh sách nhãn
    # -----------------------------
    def combine_edit_prompts(self, label_keys: List[str]) -> Tuple[List[str], List[EditPrompt]]:
        # Bảo vệ đầu vào rỗng (không nên xảy ra trong pipeline bình thường)
        if not label_keys:
            raise ValueError("combine_edit_prompts(): label_keys is empty")

        # Lọc nhận các nhãn có trong map; giữ thứ tự input
        valid_labels = self._valid_input_labels(label_keys)
        # Nếu không còn nhãn hợp lệ sau lọc → cấu hình map thiếu; báo lỗi để sửa config
        if not valid_labels:
            raise ValueError(f"No mapped labels for input: {label_keys}")

        # Chiến lược duy nhất: UNION (theo yêu cầu) + DEDUPE (đã thực hiện trong union)
        eids = self._union_eids_by_input_order(valid_labels)

        # Sắp xếp theo compose.global_prompt_order (bắt buộc đủ)
        eids = self._order_by_global(eids)

        # Chuyển danh sách id sang danh sách EditPrompt đối tượng
        edit_prompts = [self._edit_prompts_by_id[eid] for eid in eids]

        # Trả lại cặp (các nhãn hợp lệ theo thứ tự input, danh sách quy tắc theo thứ tự cuối)
        return valid_labels, edit_prompts

    # -----------------------------
    # API: sinh system prompt hoàn chỉnh cho LLM
    # -----------------------------
    def build_system_prompt(self, label_keys: List[str]) -> Tuple[str, List[str], List[str]]:
        # Gọi combine_edit_prompts để lấy danh sách quy tắc đã hợp + sắp xếp
        selected_labels, edit_prompts = self.combine_edit_prompts(label_keys)

        # Lấy system base từ compose (hoặc mặc định)
        base = self.base_system_prompt().rstrip()

        # Kết hợp nội dung text của từng quy tắc thành bullet theo thứ tự đã quyết định
        bullets = "\n".join(f"- {ep.text}" for ep in edit_prompts)

        # Lắp ghép thành system prompt cuối cùng (yêu cầu chỉ trả về văn bản đã chỉnh sửa)
        system_prompt = (
            f"{base}\n\n"
            f"Yêu cầu chỉnh sửa (thực hiện theo thứ tự):\n{bullets}\n"
            f"Chỉ trả về văn bản đã chỉnh sửa, không kèm giải thích."
        )

        # Trả thêm danh sách id quy tắc (phục vụ audit/lưu vết)
        ep_ids = [ep.id for ep in edit_prompts]

        # Trả về bộ 3: (system_prompt, selected_labels, edit_prompt_ids)
        return system_prompt, selected_labels, ep_ids
