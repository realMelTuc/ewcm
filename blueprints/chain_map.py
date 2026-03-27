from flask import Blueprint, render_template, jsonify, request
from db import get_db, serialize_row

bp = Blueprint('chain_map', __name__)


@bp.route('/chain-map/')
def chain_map():
    return render_template('partials/chain_map/index.html')


@bp.route('/api/chain-map/chains')
def list_active_chains():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, name, home_system, status, created_at, updated_at
        FROM ewcm_chains
        WHERE status = 'active'
        ORDER BY updated_at DESC
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify([serialize_row(r) for r in rows])


@bp.route('/api/chain-map/chain/<chain_id>')
def get_chain_map(chain_id):
    """Return full graph data (nodes + connections) for a chain."""
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, name, home_system, status, notes, created_at, updated_at
        FROM ewcm_chains WHERE id = %s
    """, (chain_id,))
    chain = cur.fetchone()
    if not chain:
        cur.close()
        conn.close()
        return jsonify({'error': 'not found'}), 404

    cur.execute("""
        SELECT id, system_name, wh_class, static1, static2, effect,
               is_home, notes, pos_x, pos_y, created_at
        FROM ewcm_nodes
        WHERE chain_id = %s
        ORDER BY is_home DESC, created_at ASC
    """, (chain_id,))
    nodes = [serialize_row(r) for r in cur.fetchall()]

    cur.execute("""
        SELECT cn.id, cn.from_node_id, cn.to_node_id,
               cn.wh_type, cn.wh_size, cn.mass_status, cn.time_status,
               cn.sig_id_from, cn.sig_id_to, cn.notes, cn.updated_at,
               n1.system_name AS from_system,
               n2.system_name AS to_system
        FROM ewcm_connections cn
        JOIN ewcm_nodes n1 ON n1.id = cn.from_node_id
        JOIN ewcm_nodes n2 ON n2.id = cn.to_node_id
        WHERE cn.chain_id = %s
        ORDER BY cn.created_at ASC
    """, (chain_id,))
    connections = [serialize_row(r) for r in cur.fetchall()]

    cur.close()
    conn.close()
    return jsonify({
        'chain': serialize_row(chain),
        'nodes': nodes,
        'connections': connections
    })


@bp.route('/api/chain-map/chain/<chain_id>/nodes', methods=['POST'])
def add_node(chain_id):
    data = request.get_json() or {}
    system_name = data.get('system_name', '').strip()
    if not system_name:
        return jsonify({'error': 'system_name required'}), 400

    conn = get_db()
    cur = conn.cursor()

    # Check chain exists and is active
    cur.execute("SELECT id, status FROM ewcm_chains WHERE id = %s", (chain_id,))
    chain = cur.fetchone()
    if not chain:
        cur.close()
        conn.close()
        return jsonify({'error': 'chain not found'}), 404

    wh_class = data.get('wh_class', '').strip() or None
    static1 = data.get('static1', '').strip() or None
    static2 = data.get('static2', '').strip() or None
    effect = data.get('effect', '').strip() or None
    notes = data.get('notes', '').strip() or None
    is_home = bool(data.get('is_home', False))
    pos_x = float(data.get('pos_x', 400))
    pos_y = float(data.get('pos_y', 300))

    cur.execute("""
        INSERT INTO ewcm_nodes
            (chain_id, system_name, wh_class, static1, static2, effect, is_home, notes, pos_x, pos_y)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id, system_name, wh_class, static1, static2, effect, is_home, notes, pos_x, pos_y, created_at
    """, (chain_id, system_name, wh_class, static1, static2, effect, is_home, notes, pos_x, pos_y))
    node = cur.fetchone()

    # Update chain timestamp
    cur.execute("UPDATE ewcm_chains SET updated_at = NOW() WHERE id = %s", (chain_id,))

    # Upsert registry
    cur.execute("""
        INSERT INTO ewcm_system_registry (system_name, wh_class, static1, static2, effect, visit_count, last_visited_at)
        VALUES (%s, %s, %s, %s, %s, 1, NOW())
        ON CONFLICT (system_name) DO UPDATE
        SET visit_count = ewcm_system_registry.visit_count + 1,
            last_visited_at = NOW(),
            wh_class = COALESCE(%s, ewcm_system_registry.wh_class),
            static1 = COALESCE(%s, ewcm_system_registry.static1),
            static2 = COALESCE(%s, ewcm_system_registry.static2),
            effect = COALESCE(%s, ewcm_system_registry.effect)
    """, (system_name, wh_class, static1, static2, effect,
          wh_class, static1, static2, effect))

    conn.commit()
    cur.close()
    conn.close()
    return jsonify(serialize_row(node) if node else {}), 201


@bp.route('/api/chain-map/nodes/<node_id>', methods=['PUT'])
def update_node(node_id):
    data = request.get_json() or {}
    conn = get_db()
    cur = conn.cursor()
    fields = []
    vals = []
    for k in ('system_name', 'wh_class', 'static1', 'static2', 'effect', 'notes', 'pos_x', 'pos_y'):
        if k in data:
            fields.append(f'{k} = %s')
            vals.append(data[k] if data[k] != '' else None)
    if not fields:
        return jsonify({'error': 'nothing to update'}), 400
    vals.append(node_id)
    cur.execute(
        f"UPDATE ewcm_nodes SET {', '.join(fields)} WHERE id = %s RETURNING *",
        vals
    )
    row = cur.fetchone()
    # Update chain timestamp
    if row:
        cur.execute("UPDATE ewcm_chains SET updated_at = NOW() WHERE id = %s", (row['chain_id'],))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify(serialize_row(row) if row else {})


@bp.route('/api/chain-map/nodes/<node_id>', methods=['DELETE'])
def delete_node(node_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT chain_id FROM ewcm_nodes WHERE id = %s", (node_id,))
    row = cur.fetchone()
    cur.execute("DELETE FROM ewcm_nodes WHERE id = %s", (node_id,))
    if row:
        cur.execute("UPDATE ewcm_chains SET updated_at = NOW() WHERE id = %s", (row['chain_id'],))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({'ok': True})


@bp.route('/api/chain-map/chain/<chain_id>/connections', methods=['POST'])
def add_connection(chain_id):
    data = request.get_json() or {}
    from_node_id = data.get('from_node_id', '').strip()
    to_node_id = data.get('to_node_id', '').strip()
    if not from_node_id or not to_node_id:
        return jsonify({'error': 'from_node_id and to_node_id required'}), 400

    conn = get_db()
    cur = conn.cursor()

    # Verify both nodes belong to this chain
    cur.execute("""
        SELECT id FROM ewcm_nodes
        WHERE id IN (%s, %s) AND chain_id = %s
    """, (from_node_id, to_node_id, chain_id))
    if len(cur.fetchall()) < 2:
        cur.close()
        conn.close()
        return jsonify({'error': 'nodes not found in this chain'}), 400

    wh_type = data.get('wh_type', 'K162').strip() or 'K162'
    wh_size = data.get('wh_size', 'large').strip() or 'large'
    mass_status = data.get('mass_status', 'fresh').strip() or 'fresh'
    time_status = data.get('time_status', 'fresh').strip() or 'fresh'
    sig_id_from = data.get('sig_id_from', '').strip() or None
    sig_id_to = data.get('sig_id_to', '').strip() or None
    notes = data.get('notes', '').strip() or None

    cur.execute("""
        INSERT INTO ewcm_connections
            (chain_id, from_node_id, to_node_id, wh_type, wh_size,
             mass_status, time_status, sig_id_from, sig_id_to, notes)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id, from_node_id, to_node_id, wh_type, wh_size,
                  mass_status, time_status, sig_id_from, sig_id_to, notes, created_at
    """, (chain_id, from_node_id, to_node_id, wh_type, wh_size,
          mass_status, time_status, sig_id_from, sig_id_to, notes))
    row = cur.fetchone()
    cur.execute("UPDATE ewcm_chains SET updated_at = NOW() WHERE id = %s", (chain_id,))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify(serialize_row(row) if row else {}), 201


@bp.route('/api/chain-map/connections/<connection_id>', methods=['PUT'])
def update_connection(connection_id):
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
    vals.append(connection_id)
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


@bp.route('/api/chain-map/connections/<connection_id>', methods=['DELETE'])
def delete_connection(connection_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT chain_id FROM ewcm_connections WHERE id = %s", (connection_id,))
    row = cur.fetchone()
    cur.execute("DELETE FROM ewcm_connections WHERE id = %s", (connection_id,))
    if row:
        cur.execute("UPDATE ewcm_chains SET updated_at = NOW() WHERE id = %s", (row['chain_id'],))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({'ok': True})
