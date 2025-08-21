def assign_seats(passengers, seats):
    """
    Asigna asientos a pasajeros cumpliendo reglas:
    - Menores deben sentarse al lado de un adulto de su misma compra.
    - Pasajeros de la misma compra se asignan lo más juntos posible.
    - No mezclar clases (seat_type_id).
    """
    if not passengers:
        return []

    # Crear diccionario de asientos por ID para fácil acceso
    seats_by_id = {s['seat_id']: s for s in seats}
    
    # Marcar asientos ocupados
    occupied = {p['seat_id'] for p in passengers if p['seat_id'] is not None}

    # Agrupar por purchase_id
    groups = {}
    for p in passengers:
        groups.setdefault(p['purchase_id'], []).append(p)

    # Organizar asientos por clase y por fila/columna
    seats_by_type = {}
    for s in seats:
        seats_by_type.setdefault(s['seat_type_id'], []).append(s)
    
    # Ordenar asientos por fila y columna
    for seat_type_id in seats_by_type:
        seats_by_type[seat_type_id].sort(key=lambda x: (x['seat_row'], x['seat_column']))

    assigned = []

    # Procesar cada grupo de compra
    for purchase_id, group in groups.items():
        # Separar adultos y menores
        adults = [p for p in group if p['age'] >= 18]
        minors = [p for p in group if p['age'] < 18]
        
        # Si no hay adultos, tratar a todos como adultos (para asignación)
        if not adults:
            adults = minors
            minors = []
        
        # Asignar adultos primero, buscando bloques de asientos contiguos
        adult_assignments = []
        for adult in adults:
            if adult['seat_id']:  # ya asignado en BD
                adult_assignments.append(adult)
                continue
                
            seat_type_id = adult['seat_type_id']
            available = [s for s in seats_by_type.get(seat_type_id, []) if s['seat_id'] not in occupied]
            
            if not available:
                adult['seat_id'] = None
                adult_assignments.append(adult)
                continue
            
            # Intentar encontrar un bloque de asientos para el grupo
            if len(adults) > 1:
                # Buscar bloque de asientos contiguos
                block = find_seat_block(available, len(adults))
                if block:
                    for i, adult in enumerate(adults):
                        if not adult['seat_id']:  # Si aún no tiene asiento
                            chosen = block[i] if i < len(block) else available[0]
                            adult['seat_id'] = chosen['seat_id']
                            occupied.add(chosen['seat_id'])
                    adult_assignments.extend(adults)
                    continue
            
            # Si no se encuentra bloque, asignar individualmente
            chosen = available[0]
            adult['seat_id'] = chosen['seat_id']
            occupied.add(chosen['seat_id'])
            adult_assignments.append(adult)
        
        # Ahora asignar menores cerca de los adultos del grupo
        for minor in minors:
            if minor['seat_id']:  # ya asignado en BD
                assigned.append(minor)
                continue
                
            seat_type_id = minor['seat_type_id']
            available = [s for s in seats_by_type.get(seat_type_id, []) if s['seat_id'] not in occupied]
            
            if not available:
                minor['seat_id'] = None
                assigned.append(minor)
                continue
            
            # Buscar asientos de adultos del mismo grupo
            adult_seats = [p['seat_id'] for p in adult_assignments if p['seat_id']]
            
            # Si hay adultos con asientos asignados, buscar asientos cercanos
            if adult_seats:
                # Obtener información de los asientos de adultos
                adult_seat_info = [seats_by_id[seat_id] for seat_id in adult_seats if seat_id in seats_by_id]
                
                # Buscar asientos cercanos a los adultos
                best_seat = None
                min_distance = float('inf')
                
                for seat in available:
                    for adult_seat in adult_seat_info:
                        # Calcular distancia basada en fila y columna
                        row_diff = abs(seat['seat_row'] - adult_seat['seat_row'])
                        col_diff = abs(ord(seat['seat_column']) - ord(adult_seat['seat_column']))
                        distance = row_diff + col_diff
                        
                        if distance < min_distance:
                            min_distance = distance
                            best_seat = seat
                
                if best_seat and min_distance <= 2:  # Máximo 2 unidades de distancia (fila+columna)
                    chosen = best_seat
                else:
                    # Si no encontramos asiento cercano, tomar el primero disponible
                    chosen = available[0]
            else:
                # Si no hay adultos, asignar el primer asiento disponible
                chosen = available[0]
            
            minor['seat_id'] = chosen['seat_id']
            occupied.add(chosen['seat_id'])
            assigned.append(minor)
        
        # Agregar adultos a la lista final
        assigned.extend(adult_assignments)

    return assigned

def find_seat_block(available_seats, group_size):
    """
    Encuentra un bloque de asientos contiguos para un grupo
    """
    # Agrupar asientos por fila
    seats_by_row = {}
    for seat in available_seats:
        if seat['seat_row'] not in seats_by_row:
            seats_by_row[seat['seat_row']] = []
        seats_by_row[seat['seat_row']].append(seat)
    
    # Ordenar asientos por columna en cada fila
    for row in seats_by_row:
        seats_by_row[row].sort(key=lambda x: x['seat_column'])
    
    # Buscar en cada fila un bloque del tamaño requerido
    for row, seats_in_row in seats_by_row.items():
        if len(seats_in_row) >= group_size:
            # Verificar si hay asientos consecutivos
            for i in range(len(seats_in_row) - group_size + 1):
                # Verificar si los asientos son consecutivos
                consecutive = True
                for j in range(1, group_size):
                    if ord(seats_in_row[i+j]['seat_column']) - ord(seats_in_row[i+j-1]['seat_column']) != 1:
                        consecutive = False
                        break
                
                if consecutive:
                    return seats_in_row[i:i+group_size]
    
    return None