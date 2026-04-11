"""
Database routers for multi-database setup.
"""


class AuthRouter:
    """
    Router for Django authentication and authorization models.

    Routes all auth-related models to the dedicated auth_db:
    - auth.User, auth.Group, auth.Permission
    - contenttypes.ContentType (required for permissions)
    - sessions.Session
    - admin.LogEntry
    """

    AUTH_APPS = {'auth', 'contenttypes', 'sessions', 'admin'}

    def db_for_read(self, model, **hints):
        """Direct read operations for auth models to auth_db."""
        if model._meta.app_label in self.AUTH_APPS:
            return 'auth_db'
        return None

    def db_for_write(self, model, **hints):
        """Direct write operations for auth models to auth_db."""
        if model._meta.app_label in self.AUTH_APPS:
            return 'auth_db'
        return None

    def allow_relation(self, obj1, obj2, **hints):
        """Allow relations between auth models or defer to next router."""
        if obj1._meta.app_label in self.AUTH_APPS and obj2._meta.app_label in self.AUTH_APPS:
            return True
        if obj1._meta.app_label in self.AUTH_APPS or obj2._meta.app_label in self.AUTH_APPS:
            # Defer to let cross-database FKs with db_constraint=False work
            # (e.g. TicketRequest.requester referencing auth_db User).
            return None
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """Ensure auth models are only migrated to auth_db."""
        if app_label in self.AUTH_APPS:
            return db == 'auth_db'
        return None


class WarehouseRouter:
    """
    Router for warehouse metadata and Fair Genomes data.

    - 'fair_genomes' app models -> fair_genomes_db
    - 'warehouse' app models -> metadata_db
    - 'ticketing' app models -> default
    - Everything else -> default
    """

    def db_for_read(self, model, **hints):
        """Direct read operations to appropriate database."""
        if model._meta.app_label == 'fair_genomes':
            return 'fair_genomes_db'
        if model._meta.app_label == 'warehouse':
            return 'metadata_db'
        if model._meta.app_label == 'ticketing':
            return 'default'
        return 'default'

    def db_for_write(self, model, **hints):
        """Direct write operations to appropriate database."""
        if model._meta.app_label == 'fair_genomes':
            return 'fair_genomes_db'
        if model._meta.app_label == 'warehouse':
            return 'metadata_db'
        if model._meta.app_label == 'ticketing':
            return 'default'
        return 'default'

    def allow_relation(self, obj1, obj2, **hints):
        """Allow relations if models are in the same database."""
        db1 = self.db_for_read(obj1.__class__)
        db2 = self.db_for_read(obj2.__class__)
        return db1 == db2

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """Ensure models are created in the correct database."""
        if app_label == 'fair_genomes':
            return db == 'fair_genomes_db'
        if app_label == 'warehouse':
            return db == 'metadata_db'
        if app_label == 'ticketing':
            return db == 'default'
        return db == 'default'
