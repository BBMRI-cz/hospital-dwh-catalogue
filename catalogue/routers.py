"""Database routers for the multi-database setup."""

AUTH_APPS = frozenset({'auth', 'contenttypes', 'sessions', 'admin'})
APP_DATABASES = {
    **dict.fromkeys(AUTH_APPS, 'auth_db'),
    'fair_genomes': 'fair_genomes_db',
    'warehouse': 'metadata_db',
    'ticketing': 'default',
    'frontend': 'default',
    'schema_registry': 'default',
}
ALLOWED_CROSS_DATABASE_RELATIONS = frozenset(
    {
        frozenset({'auth', 'ticketing'}),
    }
)


def database_for_app(app_label: str) -> str:
    """Return the configured database alias for an app label."""
    return APP_DATABASES.get(app_label, 'default')


class AuthRouter:
    """
    Router for Django authentication and authorization models.

    Routes all auth-related models to the dedicated auth_db:
    - auth.User, auth.Group, auth.Permission
    - contenttypes.ContentType (required for permissions)
    - sessions.Session
    - admin.LogEntry
    """

    def db_for_read(self, model, **hints):
        """Direct read operations for auth models to auth_db."""
        if model._meta.app_label in AUTH_APPS:
            return 'auth_db'
        return None

    def db_for_write(self, model, **hints):
        """Direct write operations for auth models to auth_db."""
        if model._meta.app_label in AUTH_APPS:
            return 'auth_db'
        return None

    def allow_relation(self, obj1, obj2, **hints):
        """Allow relations between auth models or defer to next router."""
        if obj1._meta.app_label in AUTH_APPS and obj2._meta.app_label in AUTH_APPS:
            return True
        if obj1._meta.app_label in AUTH_APPS or obj2._meta.app_label in AUTH_APPS:
            # Defer to let cross-database FKs with db_constraint=False work
            # (e.g. TicketRequest.requester referencing auth_db User).
            return None
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """Ensure auth models are only migrated to auth_db."""
        if app_label in AUTH_APPS:
            return db == 'auth_db'
        return None


class WarehouseRouter:
    """
    Router for warehouse metadata and FAIR Genomes data.

    - 'fair_genomes' app models -> fair_genomes_db
    - 'warehouse' app models -> metadata_db
    - 'ticketing' app models -> default
    - Everything else -> default
    """

    def db_for_read(self, model, **hints):
        """Direct read operations to appropriate database."""
        if model._meta.app_label in AUTH_APPS:
            return None
        return database_for_app(model._meta.app_label)

    def db_for_write(self, model, **hints):
        """Direct write operations to appropriate database."""
        if model._meta.app_label in AUTH_APPS:
            return None
        return database_for_app(model._meta.app_label)

    def allow_relation(self, obj1, obj2, **hints):
        """Allow same-database relations and documented cross-database relations."""
        app_pair = frozenset({obj1._meta.app_label, obj2._meta.app_label})
        if app_pair in ALLOWED_CROSS_DATABASE_RELATIONS:
            return True

        db1 = database_for_app(obj1._meta.app_label)
        db2 = database_for_app(obj2._meta.app_label)
        return db1 == db2

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """Ensure managed models are created in the correct database."""
        if app_label == 'fair_genomes':
            return db == 'fair_genomes_db'
        if app_label == 'warehouse':
            return False
        if app_label == 'ticketing':
            return db == 'default'
        return db == 'default'
