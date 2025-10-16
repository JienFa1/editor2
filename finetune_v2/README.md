finetune-v2 – Semantic Label Pipeline
====================================

This variant keeps the original editing pipeline but replaces the label
classifier with a FAISS semantic similarity lookup. The workflow is:

1. Prepare a descriptive paragraph for each registry label name.
2. Embed those descriptions and build the FAISS index once.
3. Run the API (`api_v2.py`) to process DOCX/big-text inputs exactly like the
   original `api.py`, now using semantic label matching.

Setup
-----

```
pip install -r editor/requirements.txt
```

Building the label index
------------------------

1. Edit `semantic_index/label_descriptions.json` (if the file does not exist,
   run the build script once and it will generate a template). Each entry
   should include:

   ```json
   {
     "name": "Tường thuật sự kiện Thánh lễ",
     "description": "Đoạn mô tả tiêu biểu cho nhãn này..."
   }
   ```

2. Run the builder:

   ```
   python -m finetune_v2.build_label_index
   ```

   This writes the FAISS index to `semantic_index/label_index.faiss` and
   `semantic_index/label_index_meta.json`. Rebuild whenever the descriptions
   change.

Running the API
---------------

```
python api_v2.py
```

The HTTP schema mirrors the original service:

- `POST /process` accepts either `big_text` or `docx_path`.
- `POST /process/default` and `/process/default_async` reuse
  `Config.DOCUMENT`.
- `GET /result/{job_id}` and `/result/{job_id}/text` expose async results.

Additional notes
----------------

- Configure embedding model, FAISS paths, and similarity thresholds in
  `editor/Config.py`.
- The semantic matcher currently returns the top label (`SIMILARITY_TOP_K=1`)
  whose cosine similarity passes the optional threshold. Adjust these values
  if you want multiple labels per chunk.
- All registry, LLM, and document settings are shared with the legacy
  `editor.Config`, so existing pipelines and prompts continue working.
