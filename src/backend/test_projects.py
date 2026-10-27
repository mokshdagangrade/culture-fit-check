"""Project ownership and conversation isolation without a live MongoDB."""
import sys
import unittest
from unittest.mock import MagicMock, patch

with patch.dict(sys.modules, {'db': MagicMock()}):
    import main
from fastapi import HTTPException
from models import ProjectCreate


class ProjectTests(unittest.TestCase):
    def test_project_lookup_requires_owner(self):
        with patch.object(main, 'projects_collection') as projects:
            projects.find_one.return_value = None
            with self.assertRaises(HTTPException) as error:
                main.owned_project('012345678901234567890123', {'_id': 'other-user'})
            self.assertEqual(error.exception.status_code, 404)
            self.assertEqual(projects.find_one.call_args.args[0]['user_id'], 'other-user')

    def test_invalid_id_returns_not_found(self):
        with self.assertRaises(HTTPException) as error:
            main.owned_project('invalid', {'_id': 'user'})
        self.assertEqual(error.exception.status_code, 404)

    def test_history_is_scoped_to_project_and_user(self):
        with patch.object(main, 'history_collection') as history:
            history.find.return_value.sort.return_value.limit.return_value = []
            main.recent_history({'_id': 'user'}, 'project-a')
            history.find.assert_called_once_with({'user_id': 'user', 'project_id': 'project-a'})

    def test_blank_name_is_rejected(self):
        with self.assertRaises(HTTPException) as error:
            main.create_project(ProjectCreate(name='   '), {'_id': 'user', 'email': 'user@example.com'})
        self.assertEqual(error.exception.status_code, 400)

    def test_private_database_fields_are_not_returned(self):
        project = main.project_json({'_id': 'project', 'user_id': 'secret', 'name': 'Launch'})
        self.assertEqual(project, {'id': 'project', 'name': 'Launch'})


if __name__ == '__main__':
    unittest.main()
