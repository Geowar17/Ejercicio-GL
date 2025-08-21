def assign_seats(passengers, seats):
    """
    Asigna asientos a pasajeros cumpliendo reglas:
    - Menores deben sentarse al lado de un adulto de su misma compra.
    - Pasajeros de la misma compra se asignan lo más juntos posible.
    - No mezclar clases (seat_type_id).
    """
    if not passengers:
        return []

    # 1. Crear diccionarios para fácil acceso y manejo
    seats_by_id = {s['seat_id']: s for s in seats}
    seats_by_type = {s_type: [] for s_type in {s['seat_type_id'] for s in seats}}
    for s in seats:
        seats_by_type[s['seat_type_id']].append(s)

    for seat_type_id in seats_by_type:
        seats_by_type[seat_type_id].sort(key=lambda x: (x['seat_row'], x['seat_column']))

    # Marcar asientos ya ocupados de la BD
    occupied = {p['seat_id'] for p in passengers if p.get('seat_id') is not None}
    
    # 2. Agrupar por purchase_id y procesar
    groups = {}
    for p in passengers:
        groups.setdefault(p['purchase_id'], []).append(p)
    
    final_passengers = []
    
    # 3. Iterar sobre cada grupo de compra
    for _, group in groups.items():
        # Separar adultos y menores
        adults = [p for p in group if p['age'] >= 18]
        minors = [p for p in group if p['age'] < 18]
        
        group_assigned_passengers = []
        
        # 4. Asignar asientos a los adultos que no tienen asiento
        for adult in adults:
            if adult.get('seat_id') is not None:
                group_assigned_passengers.append(adult)
                continue

            seat_type_id = adult['seat_type_id']
            available_seats = [s for s in seats_by_type.get(seat_type_id, []) if s['seat_id'] not in occupied]
            
            if available_seats:
                chosen_seat = available_seats[0]  # Tomar el primer asiento disponible
                adult['seat_id'] = chosen_seat['seat_id']
                occupied.add(chosen_seat['seat_id'])
            else:
                adult['seat_id'] = None
            
            group_assigned_passengers.append(adult)
            
        # 5. Asignar asientos a los menores
        for minor in minors:
            if minor.get('seat_id') is not None:
                group_assigned_passengers.append(minor)
                continue
                
            seat_type_id = minor['seat_type_id']
            available_seats = [s for s in seats_by_type.get(seat_type_id, []) if s['seat_id'] not in occupied]
            
            if available_seats:
                # Lógica simplificada: buscar el asiento más cercano a un adulto
                best_seat = None
                min_distance = float('inf')
                
                # Obtener la lista de asientos de adultos ya asignados en este grupo
                adult_seat_ids = [p['seat_id'] for p in group_assigned_passengers if p.get('seat_id') is not None and p['age'] >= 18]
                adult_seats_info = [seats_by_id[sid] for sid in adult_seat_ids if sid in seats_by_id]
                
                if adult_seats_info:
                    for seat in available_seats:
                        for adult_seat in adult_seats_info:
                            distance = abs(seat['seat_row'] - adult_seat['seat_row']) + abs(ord(seat['seat_column']) - ord(adult_seat['seat_column']))
                            if distance < min_distance:
                                min_distance = distance
                                best_seat = seat
                
                if best_seat:
                    chosen_seat = best_seat
                else:
                    chosen_seat = available_seats[0]

                minor['seat_id'] = chosen_seat['seat_id']
                occupied.add(chosen_seat['seat_id'])
            else:
                minor['seat_id'] = None

            group_assigned_passengers.append(minor)
            
        # 6. Agregar todos los pasajeros del grupo a la lista final
        final_passengers.extend(group_assigned_passengers)
        
    return final_passengers

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