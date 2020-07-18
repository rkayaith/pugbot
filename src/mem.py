from collections import defaultdict

# this is stored in a seperate module so that
# it persists even when 'rewrite' is reloaded
chan_ctxs = defaultdict()
