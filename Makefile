# One-command workflows for reproducibility.
.PHONY: help setup manual corpus mddb index ingest serve ui eval eval-ir clean

help:
	@echo "Targets:"
	@echo "  setup     Install Python + Node deps"
	@echo "  manual    Crawl+organize a model's manual(s): make manual BRAND=volvo MODEL=v40 VARIANT=4-door/2012-2019 (VARIANT optional -- omit for every variant of that model)"
	@echo "  corpus    Crawl+organize every model for one brand: make corpus BRAND=volvo"
	@echo "  manifest  Build the metadata bridge (data/stores/manuals.sqlite)"
	@echo "  index-brand  Index one/some brands IN PLACE: make index-brand BRANDS=honda"
	@echo "  index     Chunk, embed, and index ALL brands (long; resumable)"
	@echo "  ingest    Full ingestion: manifest + index"
	@echo "  serve     Run the FastAPI endpoint"
	@echo "  ui        Run the Streamlit UI"
	@echo "  eval      Run RAGAS evaluation"
	@echo "  eval-ir   Run retrieval metrics (Recall@k/MRR/NDCG)"

setup:
	pip install -r requirements.txt
	cd mddb && npm install

# Downloads mycarusermanual.com content into data/manuals/<brand>/<model>/<variant>/,
# organized folder-per-section with images + a bundled PDF + a manifest.
# Separate from mddb/index, which read the (unrelated) flat data/markdown/ corpus.
manual:
	python -m app.ingest.run "$(BRAND)" "$(MODEL)" "$(VARIANT)"

corpus:
	python -m app.ingest.crawl "$(BRAND)"

mddb:
	cd mddb && node build.mjs

# The metadata bridge: derive make/year/manual_id from the crawled tree and
# write data/stores/manuals.sqlite (used for query-time vehicle scoping).
manifest:
	python -m app.ingest.manifest

# Chunk + embed + index the manuals corpus IN PLACE (data/manuals/), resumable
# brand-by-brand. Index one brand:  make index-brand BRANDS=honda
# Index everything (long):          make index
index-brand: manifest
	python -m app.ingest.build_index --brands "$(BRANDS)"

index: manifest
	python -m app.ingest.build_index --all

ingest: manifest index
	@echo "Ingestion complete."

serve:
	uvicorn app.api:app --reload

ui:
	streamlit run app/ui.py

eval:
	python -m eval.run_ragas

eval-ir:
	python -m eval.run_ir

clean:
	rm -rf data/stores/* __pycache__ app/**/__pycache__
