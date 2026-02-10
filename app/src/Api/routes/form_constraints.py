from flask import Blueprint, jsonify

from ..services.form_constraints import get_public_form_constraints_config

bp = Blueprint("api_form_constraints", __name__)


@bp.get("/api/form-constraints")
def get_form_constraints():
    return jsonify(get_public_form_constraints_config())
