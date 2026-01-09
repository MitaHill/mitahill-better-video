# Current Issues

## 1. Migration Status
- **Flask + Vue migration in progress**: Streamlit UI has been removed, Vue UI is now served by Flask.
- **Docker images**: Ensure `deploy/docker/for-app/Dockerfile` builds the frontend assets during image build.

## 2. Pending Validation
- **API polling**: Validate `GET /api/tasks/<task_id>` response under concurrent usage.
- **Preview availability**: Preview endpoints return 404 until worker generates previews.
