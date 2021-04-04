"""load python modules by path"""
import importlib


def import_by_path(target):
    """import target based on python path"""
    if isinstance(target, str):
        modnam, funnam = target.rsplit('.', 1)
        mod = importlib.import_module(modnam)
        return getattr(mod, funnam)
    return target
