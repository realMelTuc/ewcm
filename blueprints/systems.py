from flask import Blueprint, render_template, jsonify, request
from db import get_db, serialize_row

bp = Blueprint('systems', __name__)


@bp.route('/systems/')
def systems():
    return render_template('partials/systems/index.html')


@bp.route('/api/systems', methods=['GET'])
def list_systems():
    search = request.args.get('q', '').strip()
    wh_class = request.args.get('wh_class', '').strip()
    conn = get_db()
    cur = conn.cursor()

    where = []
    params = []
    if search:
        where.append("system_name ILIKE %s")
        params.append(f'%{search}%')
    if wh_class:
        where.append("wh_class = %s")
        params.append(wh_class)

    sql = """
        SELECT id, system_name, wh_class, static1, static2, effect,
               region, notes, visit_count, last_visited_at, created_at
        FROM ewcm_system_registry
    """
    if where:
        sql += ' WHERE ' + ' AND '.join(where)
    sql += ' ORDER BY last_visited_at DESC NULLS LAST, visit_count DESC LIMIT 200'

    cur.execute(sql, params)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify([serialize_row(r) for r in rows])


@bp.route('/api/systems/<system_name>', methods=['GET'])
def get_system(system_name):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, system_name, wh_class, static1, static2, effect,
               region, notes, visit_count, last_visited_at, created_at
        FROM ewcm_system_registry WHERE system_name = %s
    """, (system_name,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return jsonify({'error': 'not found'}), 404
    return jsonify(serialize_row(row))


@bp.route('/api/systems', methods=['POST'])
def create_system():
    data = request.get_json() or {}
    system_name = data.get('system_name', '').strip()
    if not system_name:
        return jsonify({'error': 'system_name required'}), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO ewcm_system_registry
            (system_name, wh_class, static1, static2, effect, region, notes)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (system_name) DO UPDATE
        SET wh_class = COALESCE(%s, ewcm_system_registry.wh_class),
            static1 = COALESCE(%s, ewcm_system_registry.static1),
            static2 = COALESCE(%s, ewcm_system_registry.static2),
            effect = COALESCE(%s, ewcm_system_registry.effect),
            region = COALESCE(%s, ewcm_system_registry.region),
            notes = COALESCE(%s, ewcm_system_registry.notes),
            visit_count = ewcm_system_registry.visit_count + 1,
            last_visited_at = NOW()
        RETURNING *
    """, (
        system_name,
        data.get('wh_class') or None,
        data.get('static1') or None,
        data.get('static2') or None,
        data.get('effect') or None,
        data.get('region') or None,
        data.get('notes') or None,
        data.get('wh_class') or None,
        data.get('static1') or None,
        data.get('static2') or None,
        data.get('effect') or None,
        data.get('region') or None,
        data.get('notes') or None,
    ))
    row = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return jsonify(serialize_row(row) if row else {}), 201


@bp.route('/api/systems/<system_id>', methods=['PUT'])
def update_system(system_id):
    data = request.get_json() or {}
    conn = get_db()
    cur = conn.cursor()
    fields = []
    vals = []
    for k in ('system_name', 'wh_class', 'static1', 'static2', 'effect', 'region', 'notes'):
        if k in data:
            fields.append(f'{k} = %s')
            vals.append(data[k] if data[k] != '' else None)
    if not fields:
        return jsonify({'error': 'nothing to update'}), 400
    vals.append(system_id)
    cur.execute(
        f"UPDATE ewcm_system_registry SET {', '.join(fields)} WHERE id = %s RETURNING *",
        vals
    )
    row = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return jsonify(serialize_row(row) if row else {})


@bp.route('/api/systems/<system_id>', methods=['DELETE'])
def delete_system(system_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM ewcm_system_registry WHERE id = %s", (system_id,))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({'ok': True})


@bp.route('/api/systems/autocomplete')
def autocomplete():
    q = request.args.get('q', '').strip()
    if len(q) < 1:
        return jsonify([])
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT system_name, wh_class, static1, effect
        FROM ewcm_system_registry
        WHERE system_name ILIKE %s
        ORDER BY visit_count DESC
        LIMIT 10
    """, (f'{q}%',))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify([serialize_row(r) for r in rows])
