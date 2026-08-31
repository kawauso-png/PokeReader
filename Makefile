.PHONY: all clean lint test prepare
LIBPOKEREADER := reader_core/target/armv6k-nintendo-3ds/release/libpokereader.a
PHASE_PREP := prepare_blue_divphase_v12.sh
FORECAST_PREP := prepare_blue_forecast_v19.sh
AUTOPAUSE_PREP := prepare_blue_autopause_v20.sh
AUTOPAUSE_NOW_PREP := prepare_blue_autopause_now_v21.sh
PLUS4_PREP := prepare_blue_plus4_v22.sh
LEGEND_PREP := prepare_blue_legend_v23.sh
ZAPDOS_PREP := prepare_blue_zapdos_v24.sh
MOLTRES_PREP := prepare_blue_moltres_v25.sh
MOLTRES_PHASEFIX_PREP := prepare_blue_moltres_phasefix_v26.sh
MOLTRES_GBSEQ_PREP := prepare_blue_moltres_gbseq_v27.sh
ADAPT_BADROWS_PREP := prepare_blue_adaptive_badrows_v28.sh
ADAPT_SPECIAL_PREP := prepare_blue_adaptive_special_v29.sh

R_SRCS := $(shell find reader_core/src -name '*.rs')
C_SRCS := $(shell find 3gx/sources -name '*.c')
H_SRCS := $(shell find 3gx/includes -name '*.h')

all: out/default.3gx

prepare:
	sh $(PHASE_PREP)
	sh $(FORECAST_PREP)
	sh $(AUTOPAUSE_PREP)
	sh $(AUTOPAUSE_NOW_PREP)
	sh $(PLUS4_PREP)
	sh $(LEGEND_PREP)
	sh $(ZAPDOS_PREP)
	sh $(MOLTRES_PREP)
	sh $(MOLTRES_PHASEFIX_PREP)
	sh $(MOLTRES_GBSEQ_PREP)
	sh $(ADAPT_BADROWS_PREP)
	sh $(ADAPT_SPECIAL_PREP)

$(LIBPOKEREADER): prepare $(R_SRCS)
	cargo +nightly-2024-03-21 build --release -Z build-std=core,alloc --target armv6k-nintendo-3ds --manifest-path reader_core/Cargo.toml

out/default.3gx: prepare $(LIBPOKEREADER) $(C_SRCS) $(H_SRCS)
	make clean -C 3gx
	make -C 3gx
	mkdir -p out
	cp 3gx/build/3gx.3gx out/default.3gx

clean:
	cargo clean --manifest-path reader_core/Cargo.toml
	make clean -C 3gx
	rm -rf out

format: prepare
	cargo +nightly fmt --all --manifest-path reader_core/Cargo.toml

lint: prepare
	cargo +nightly-2024-03-21 clippy --release -Z build-std=core,alloc --target armv6k-nintendo-3ds --manifest-path reader_core/Cargo.toml

test: prepare
	cargo +nightly-2024-03-21 test --manifest-path reader_core/Cargo.toml
