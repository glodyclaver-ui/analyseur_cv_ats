"""Facade gestion de donnees locales : sauvegarde, restauration, integrite, purge."""
from . import _core, audit_trail_manager

read = _core.read_json
write = _core.write_json
health = _core.health
list_backups = _core.list_backups


def backup():
    n = _core.make_backup()
    audit_trail_manager.log("backup", n)
    return n


def restore(name):
    n = _core.restore_backup(name)
    audit_trail_manager.log("restore", name)
    return n


def purge(days=None):
    if days:
        return _core.purge_older_than(days)
    _core.purge_all()
    return -1
