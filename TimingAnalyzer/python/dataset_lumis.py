import subprocess

_CACHE = {}

def get_lumi_files(dataset):
    _CACHE[dataset] = {}

    files = subprocess.run(
        "dasgoclient file dataset={}".format(dataset),
        shell=True,
        save_output=True
    )

    import pdb; pdb.set_trace()
    # Run dasgoclient to get files
    # For each file run dasgoclient to get lumis for each file
    # Cache
    pass
