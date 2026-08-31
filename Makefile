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
DIVDIAG_PREP := prepare_blue_divdiag_v30.sh
NPC_RESYNC_PREP := prepare_blue_npc_resync_v31.sh
NPC_RESYNC_FIX_PREP := prepare_blue_npc_resync_fix_v32.sh
NPC_LOCALBASE_PREP := prepare_blue_npc_localbase_v33.sh
MOLTRES_PROB_RESCUE_PREP := prepare_blue_moltres_prob_rescue_v34.sh
MOLTRES_PROB_RESET_PREP := prepare_blue_moltres_prob_reset_v35.sh
MOLTRES_NOWFRAME_PREP := prepare_blue_moltres_nowframe_v36.sh
MOLTRES_VCRESET_PREP := prepare_blue_moltres_vcreset_v37.sh
MOLTRES_VCRESET_CFIX_PREP := prepare_blue_moltres_vcreset_cfix_v38.sh
ARTICUNO_CAL_PREP := prepare_blue_articuno_cal_v39.sh
ARTICUNO_AUTO_PREP := prepare_blue_articuno_auto_v40.sh
ARTICUNO_ADPFIX_PREP := prepare_blue_articuno_adpfix_v41.sh
ARTICUNO_COLDNPC_PREP := prepare_blue_articuno_coldnpc_v42.sh
ARTICUNO_COLDNPC2_PREP := prepare_blue_articuno_coldnpc2_v43.sh

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
	sh $(DIVDIAG_PREP)
	sh $(NPC_RESYNC_PREP)
	sh $(NPC_RESYNC_FIX_PREP)
	sh $(NPC_LOCALBASE_PREP)
	sh $(MOLTRES_PROB_RESCUE_PREP)
	sh $(MOLTRES_PROB_RESET_PREP)
	sh $(MOLTRES_NOWFRAME_PREP)
	sh $(MOLTRES_VCRESET_PREP)
	sh $(MOLTRES_VCRESET_CFIX_PREP)
	sh $(ARTICUNO_CAL_PREP)
	sh $(ARTICUNO_AUTO_PREP)
	sh $(ARTICUNO_ADPFIX_PREP)
	sh $(ARTICUNO_COLDNPC_PREP)
	sh $(ARTICUNO_COLDNPC2_PREP)

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
