from pathlib import Path

# v7.6.7 is now maintained directly in the apply script. Keep this wrapper so
# the existing workflow entry point stays stable, but do not rewrite the patch
# source in memory: that extra transformation layer caused brittle escaping and
# anchor failures during the first iterations.
path = Path('apply_suicune_live_pass_jitter_probe_v767.py')
source = path.read_text()
exec(compile(source, str(path), 'exec'), {'__name__': '__main__'})
