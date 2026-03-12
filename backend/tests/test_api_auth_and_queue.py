import base64

from app.core.config import settings


def _cursor_to_int(cursor: str) -> int:
    return int(base64.urlsafe_b64decode(cursor.encode('utf-8')).decode('utf-8'))


def test_queue_requires_auth(client):
    response = client.get('/api/v1/review/queue')
    assert response.status_code == 401


def test_queue_pagination_is_deterministic(client):
    login_response = client.post('/api/v1/auth/login', json={'username': 'reviewer', 'password': 'pass123'})
    assert login_response.status_code == 200

    first = client.get('/api/v1/review/queue?limit=1')
    assert first.status_code == 200
    data1 = first.json()
    assert len(data1['items']) == 1
    assert data1['items'][0]['group_key'] == 'alpha'
    assert data1['next_cursor'] is not None

    second = client.get(f"/api/v1/review/queue?limit=1&cursor={data1['next_cursor']}")
    assert second.status_code == 200
    data2 = second.json()
    assert len(data2['items']) == 1
    assert data2['items'][0]['group_key'] == 'beta'

    assert _cursor_to_int(data1['next_cursor']) < _cursor_to_int(data2['next_cursor'])


def test_decision_requires_csrf(client):
    login_response = client.post('/api/v1/auth/login', json={'username': 'reviewer', 'password': 'pass123'})
    assert login_response.status_code == 200

    response = client.post(
        '/api/v1/review/decision',
        json={
            'group_id': 1,
            'image_id': 1,
            'state': 'keep',
            'reason_code': 'count_matches',
            'notes': ''
        }
    )
    assert response.status_code == 403


def test_direct_delete_decision_is_rejected(client):
    login_response = client.post('/api/v1/auth/login', json={'username': 'reviewer', 'password': 'pass123'})
    assert login_response.status_code == 200
    csrf_token = login_response.json()['csrf_token']

    response = client.post(
        '/api/v1/review/decision',
        headers={'X-CSRF-Token': csrf_token},
        json={
            'group_id': 1,
            'image_id': 1,
            'state': 'delete',
            'reason_code': 'extra_same_class',
            'notes': ''
        }
    )
    assert response.status_code == 400
    assert 'soft-delete' in response.json()['detail']


def test_bulk_decision_response_includes_saved_and_skipped_ids(client):
    login_response = client.post('/api/v1/auth/login', json={'username': 'reviewer', 'password': 'pass123'})
    assert login_response.status_code == 200
    csrf_token = login_response.json()['csrf_token']

    response = client.post(
        '/api/v1/review/decision/bulk',
        headers={'X-CSRF-Token': csrf_token},
        json={
            'decisions': [
                {
                    'group_id': 1,
                    'image_id': 1,
                    'state': 'keep',
                    'reason_code': 'count_matches',
                    'notes': ''
                },
                {
                    'group_id': 2,
                    'image_id': 1,
                    'state': 'keep',
                    'reason_code': 'count_matches',
                    'notes': ''
                }
            ]
        }
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload['saved'] == 1
    assert payload['saved_image_ids'] == [1]
    assert payload['skipped_image_ids'] == [1]


def test_bulk_delete_decision_is_rejected(client):
    login_response = client.post('/api/v1/auth/login', json={'username': 'reviewer', 'password': 'pass123'})
    assert login_response.status_code == 200
    csrf_token = login_response.json()['csrf_token']

    response = client.post(
        '/api/v1/review/decision/bulk',
        headers={'X-CSRF-Token': csrf_token},
        json={
            'decisions': [
                {
                    'group_id': 1,
                    'image_id': 1,
                    'state': 'delete',
                    'reason_code': 'extra_same_class',
                    'notes': ''
                }
            ]
        }
    )
    assert response.status_code == 400
    assert 'soft-delete' in response.json()['detail']


def test_group_by_id_returns_exact_group(client):
    login_response = client.post('/api/v1/auth/login', json={'username': 'reviewer', 'password': 'pass123'})
    assert login_response.status_code == 200

    response = client.get('/api/v1/review/group/2')
    assert response.status_code == 200
    payload = response.json()
    assert payload['id'] == 2
    assert payload['group_key'] == 'beta'
    assert len(payload['generated_images']) == 1


def test_history_requires_auth(client):
    response = client.get('/api/v1/review/history')
    assert response.status_code == 401


def test_history_returns_keep_and_soft_delete(client, monkeypatch):
    monkeypatch.setattr(settings, 'enable_soft_delete', True)

    admin_login = client.post('/api/v1/auth/login', json={'username': 'admin', 'password': 'pass123'})
    assert admin_login.status_code == 200
    admin_csrf = admin_login.json()['csrf_token']

    keep_response = client.post(
        '/api/v1/review/decision',
        headers={'X-CSRF-Token': admin_csrf},
        json={
            'group_id': 1,
            'image_id': 1,
            'state': 'keep',
            'reason_code': 'count_matches',
            'notes': ''
        }
    )
    assert keep_response.status_code == 200

    delete_response = client.post('/api/v1/files/soft-delete/2', headers={'X-CSRF-Token': admin_csrf})
    assert delete_response.status_code == 200

    reviewer_login = client.post('/api/v1/auth/login', json={'username': 'reviewer', 'password': 'pass123'})
    assert reviewer_login.status_code == 200

    history_response = client.get('/api/v1/review/history?limit=20')
    assert history_response.status_code == 200
    payload = history_response.json()
    assert payload['items']
    states = {item['state'] for item in payload['items']}
    image_ids = {item['image_id'] for item in payload['items']}
    assert 'keep' in states
    assert 'delete' in states
    assert 1 in image_ids
    assert 2 in image_ids
