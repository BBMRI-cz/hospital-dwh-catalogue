"""
Tests for the catalogue project configuration.

Covers URL routing, views, and database routers.
"""

from django.contrib.auth.models import User
from django.test import TestCase

from .routers import AuthRouter, WarehouseRouter


class AuthRouterTest(TestCase):
    """Tests for the AuthRouter database router."""

    databases = {'default', 'auth_db'}

    def setUp(self):
        self.router = AuthRouter()

    def test_db_for_read_auth_model(self):
        """Auth models are routed to auth_db for reads."""
        self.assertEqual(self.router.db_for_read(User), 'auth_db')

    def test_db_for_write_auth_model(self):
        """Auth models are routed to auth_db for writes."""
        self.assertEqual(self.router.db_for_write(User), 'auth_db')

    def test_db_for_read_non_auth_model(self):
        """Non-auth models return None (defer to next router)."""
        from ticketing.models import TicketRequest

        self.assertIsNone(self.router.db_for_read(TicketRequest))

    def test_db_for_write_non_auth_model(self):
        """Non-auth models return None."""
        from ticketing.models import TicketRequest

        self.assertIsNone(self.router.db_for_write(TicketRequest))

    def test_allow_migrate_auth_to_auth_db(self):
        """Auth app can migrate to auth_db."""
        self.assertTrue(self.router.allow_migrate('auth_db', 'auth'))

    def test_allow_migrate_auth_to_default(self):
        """Auth app cannot migrate to default."""
        self.assertFalse(self.router.allow_migrate('default', 'auth'))

    def test_allow_migrate_non_auth(self):
        """Non-auth apps return None."""
        self.assertIsNone(self.router.allow_migrate('default', 'ticketing'))

    def test_allow_relation_same_auth_apps(self):
        """Relations between auth apps are allowed."""
        obj1 = User(username='test1')
        obj2 = User(username='test2')
        self.assertTrue(self.router.allow_relation(obj1, obj2))

    def test_allow_relation_auth_and_non_auth(self):
        """Relations between auth and non-auth models are blocked."""
        from ticketing.models import TicketRequest

        user = User(username='test')
        ticket = TicketRequest(requester_email='t@e.com')
        self.assertFalse(self.router.allow_relation(user, ticket))


class WarehouseRouterTest(TestCase):
    """Tests for the WarehouseRouter database router."""

    databases = {'default', 'auth_db'}

    def setUp(self):
        self.router = WarehouseRouter()

    def test_db_for_read_warehouse(self):
        """Warehouse models are routed to metadata_db."""
        from warehouse.models import DatasetList

        self.assertEqual(self.router.db_for_read(DatasetList), 'metadata_db')

    def test_db_for_read_fair_genomes(self):
        """Fair genomes models are routed to fair_genomes_db."""
        from fair_genomes.models import Personal

        self.assertEqual(self.router.db_for_read(Personal), 'fair_genomes_db')

    def test_db_for_read_ticketing(self):
        """Ticketing models are routed to default."""
        from ticketing.models import TicketRequest

        self.assertEqual(self.router.db_for_read(TicketRequest), 'default')

    def test_db_for_write_warehouse(self):
        """Warehouse models write to metadata_db."""
        from warehouse.models import DatasetList

        self.assertEqual(self.router.db_for_write(DatasetList), 'metadata_db')

    def test_db_for_write_fair_genomes(self):
        """Fair genomes models write to fair_genomes_db."""
        from fair_genomes.models import Personal

        self.assertEqual(self.router.db_for_write(Personal), 'fair_genomes_db')

    def test_db_for_write_ticketing(self):
        """Ticketing models write to default."""
        from ticketing.models import TicketRequest

        self.assertEqual(self.router.db_for_write(TicketRequest), 'default')

    def test_allow_migrate_fair_genomes(self):
        """Fair genomes can migrate to fair_genomes_db."""
        self.assertTrue(self.router.allow_migrate('fair_genomes_db', 'fair_genomes'))

    def test_allow_migrate_fair_genomes_wrong_db(self):
        """Fair genomes cannot migrate to default."""
        self.assertFalse(self.router.allow_migrate('default', 'fair_genomes'))

    def test_allow_migrate_warehouse(self):
        """Warehouse can migrate to metadata_db."""
        self.assertTrue(self.router.allow_migrate('metadata_db', 'warehouse'))

    def test_allow_migrate_ticketing(self):
        """Ticketing can migrate to default."""
        self.assertTrue(self.router.allow_migrate('default', 'ticketing'))

    def test_allow_relation_same_db(self):
        """Relations within same database are allowed."""
        from ticketing.models import TicketRequest, TicketRequestItem

        t = TicketRequest(requester_email='t@e.com')
        item = TicketRequestItem(ticket_request=t)
        self.assertTrue(self.router.allow_relation(t, item))

    def test_allow_relation_different_db(self):
        """Relations across databases are blocked."""
        from fair_genomes.models import Personal
        from ticketing.models import TicketRequest

        personal = Personal(personal_identifier='P1')
        ticket = TicketRequest(requester_email='t@e.com')
        self.assertFalse(self.router.allow_relation(personal, ticket))
