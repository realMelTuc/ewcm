from flask import Blueprint, render_template, jsonify, request
from db import get_db, serialize_row

bp = Blueprint('connections', __name__)


@bp.route('/connections/')
def connections():
    return render_template('partials/connections/index.html')


@bp.route('/api/connections', methods=['GET'])
def list_connections():
    chain_id = request.args.get('chain_id', '').strip()
    mass_status = request.args.get('mass_status', '').strip()
    time_status = request.args.get('time_status', '').strip()

    conn = get_db()
    cur = conn.cursor()

    where = []
    params = []
    if chain_id:
        where.append("cn.chain_id = %s")
        params.append(chain_id)
    if mass_status:
        where.append("cn.mass_status = %s")
        params.append(mass_status)
    if time_status:
        where.append("cn.time_status = %s")
        params.append(time_status)

    sql = """
        SELECT cn.id, cn.chain_id, cn.from_node_id, cn.to_node_id,
               cn.wh_type, cn.wh_size, cn.mass_status, cn.time_status,
               cn.sig_id_from, cn.sig_id_to, cn.notes,
               cn.created_at, cn.updated_at,
               n1.system_name AS from_system,
               n2.system_name AS to_system,
               c.name AS chain_name
        FROM ewcm_connections cn
        JOIN ewcm_nodes n1 ON n1.id = cn.from_node_id
        JOIN ewcm_nodes n2 ON n2.id = cn.to_node_id
        JOIN ewcm_chains c ON c.id = cn.chain_id
    """
    if where:
        sql += ' WHERE ' + ' AND '.join(where)
    sql += ' ORDER BY cn.updated_at DESC LIMIT 200'

    cur.execute(sql, params)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify([serialize_row(r) for r in rows])


@bp.route('/api/connections/<conn_id>', methods=['GET'])
def get_connection(conn_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT cn.*, n1.system_name AS from_system, n2.system_name AS to_system,
               c.name AS chain_name
        FROM ewcm_connections cn
        JOIN ewcm_nodes n1 ON n1.id = cn.from_node_id
        JOIN ewcm_nodes n2 ON n2.id = cn.to_node_id
        JOIN ewcm_chains c ON c.id = cn.chain_id
        WHERE cn.id = %s
    """, (conn_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return jsonify({'error': 'not found'}), 404
    return jsonify(serialize_row(row))


@bp.route('/api/connections/<conn_id>', methods=['PUT'])
def update_connection(conn_id):
    data = request.get_json() or {}
    conn = get_db()
    cur = conn.cursor()
    fields = []
    vals = []
    for k in ('wh_type', 'wh_size', 'mass_status', 'time_status', 'sig_id_from', 'sig_id_to', 'notes'):
        if k in data:
            fields.append(f'{k} = %s')
            vals.append(data[k] if data[k] != '' else None)
    if not fields:
        return jsonify({'error': 'nothing to update'}), 400
    fields.append('updated_at = NOW()')
    vals.append(conn_id)
    cur.execute(
        f"UPDATE ewcm_connections SET {', '.join(fields)} WHERE id = %s RETURNING *, chain_id",
        vals
    )
    row = cur.fetchone()
    if row:
        cur.execute("UPDATE ewcm_chains SET updated_at = NOW() WHERE id = %s", (row['chain_id'],))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify(serialize_row(row) if row else {})


@bp.route('/api/connections/<conn_id>', methods=['DELETE'])
def delete_connection(conn_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT chain_id FROM ewcm_connections WHERE id = %s", (conn_id,))
    row = cur.fetchone()
    cur.execute("DELETE FROM ewcm_connections WHERE id = %s", (conn_id,))
    if row:
        cur.execute("UPDATE ewcm_chains SET updated_at = NOW() WHERE id = %s", (row['chain_id'],))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({'ok': True})
