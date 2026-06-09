import unittest
from flask import session
from app import create_app
from app.models import db
from app.models.user import User

class TestAuthFlow(unittest.TestCase):
    def setUp(self):
        # Configure app for testing with in-memory database
        self.app = create_app({
            'TESTING': True,
            'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
            'SQLALCHEMY_TRACK_MODIFICATIONS': False,
            'SECRET_KEY': 'test-secret-key'
        })
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_register_success(self):
        response = self.client.post('/auth/register', data={
            'username': 'john_doe',
            'password': 'password123',
            'name': 'John Doe',
            'role': 'staff',
            'max_weekly_hours': '40.0',
            'max_daily_hours': '8.0'
        })
        # Verify 302 Redirect to Login
        self.assertEqual(response.status_code, 302)
        self.assertIn('/auth/login', response.location)

        # Check DB
        user = User.query.filter_by(username='john_doe').first()
        self.assertIsNotNone(user)
        self.assertEqual(user.name, 'John Doe')
        self.assertEqual(user.role, 'staff')
        self.assertTrue(user.check_password('password123'))

    def test_register_duplicate(self):
        # Create user
        User.create('john_doe', 'password123', 'John Doe', 'staff')
        
        # Try duplicate registration
        response = self.client.post('/auth/register', data={
            'username': 'john_doe',
            'password': 'newpassword',
            'name': 'Different John',
            'role': 'staff'
        })
        # Verify 400 bad request / re-render
        self.assertEqual(response.status_code, 400)

    def test_login_success(self):
        # Create user
        User.create('mary_jane', 'secretPass', 'Mary Jane', 'manager')

        # POST Login
        response = self.client.post('/auth/login', data={
            'username': 'mary_jane',
            'password': 'secretPass'
        })
        # Redirect to index
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith('/'))

        # Check session
        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get('username'), 'mary_jane')
            self.assertEqual(sess.get('role'), 'manager')

    def test_login_invalid(self):
        User.create('mary_jane', 'secretPass', 'Mary Jane', 'manager')

        # Invalid password
        response = self.client.post('/auth/login', data={
            'username': 'mary_jane',
            'password': 'wrongPassword'
        })
        self.assertEqual(response.status_code, 400)

    def test_index_redirection_unauthenticated(self):
        # Request index without session
        response = self.client.get('/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/auth/login', response.location)

    def test_index_redirection_staff(self):
        # Register and login staff
        User.create('john_staff', 'pass', 'John Staff', 'staff')
        self.client.post('/auth/login', data={'username': 'john_staff', 'password': 'pass'})

        # GET Index
        response = self.client.get('/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/dashboard/staff', response.location)

    def test_index_redirection_manager(self):
        # Register and login manager
        User.create('boss_man', 'pass', 'Boss Man', 'manager')
        self.client.post('/auth/login', data={'username': 'boss_man', 'password': 'pass'})

        # GET Index
        response = self.client.get('/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/dashboard/manager', response.location)

    def test_logout(self):
        User.create('john_staff', 'pass', 'John Staff', 'staff')
        self.client.post('/auth/login', data={'username': 'john_staff', 'password': 'pass'})

        # Logout
        response = self.client.post('/auth/logout')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/auth/login', response.location)

        # Session should be empty
        with self.client.session_transaction() as sess:
            self.assertNotIn('user_id', sess)

if __name__ == '__main__':
    unittest.main()
