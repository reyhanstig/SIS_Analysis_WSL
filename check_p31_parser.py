DEFAULT_SEASONS = ['Spring', 'Summer', 'Autumn', 'Winter']
LAYER_NAMES = {'1': 'Surface', '2': 'Bottom'}
NUTRIENT_LABELS = {'NH4N': 'NH4-N', 'NO2N': 'NO2-N', 'NO3N': 'NO3-N', 'PO4P': 'PO4-P'}

def parse_param_column(col, seasons):
    parts = col.split('_')
    if parts[0] not in seasons or len(parts) < 2:
        return 'Other', col.replace('_', ' ')
    param_season = parts[0]
    if parts[1] in LAYER_NAMES and len(parts) >= 3:
        label = '_'.join(parts[2:])
        label = NUTRIENT_LABELS.get(label, label).replace('_', ' ')
        return param_season, f"{LAYER_NAMES[parts[1]]} {label}"
    return param_season, '_'.join(parts[1:]).replace('_', ' ')

print(parse_param_column('Summer_1_WTEMP', DEFAULT_SEASONS))
print(parse_param_column('Summer_2_WTEMP', DEFAULT_SEASONS))
