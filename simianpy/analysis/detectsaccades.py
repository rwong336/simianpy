from itertools import product

import numpy as np
import pandas as pd

def DetectSaccades(eyedata, method = 'radial', velocity_threshold = 30, duration_threshold = None, sampling_rate = 1e3):
    """Detects saccades in eyedata using a velocity threshold (and optionally a duration threshold)

    Required arguments:
    eyedata (pandas.DataFrame) - must contain a pd.DatetimeIndex and columns 'eyeh' and 'eyev'

    Optional arguments:
    method (str; default = 'radial') - what is used to compute velocity; must be one of 'radial', 'horizontal', 'vertical'
    velocity_threshold (float; default = 30) - the velocity threshold in degrees per second
    duration_threshold (pd.Timedelta or None; default = None) - if not None, duration_threshold specifies minimum saccade duration
    sampling_rate (float; default = None)
    """
    #TODO Remove type checking in favor of duck typing?
    allowed_index_dtypes = pd.DatetimeIndex, pd.TimedeltaIndex
    if not isinstance(eyedata, pd.DataFrame):
        raise TypeError(f'eyedata must be pandas.DataFrame not {type(eyedata)}')
    if not any(isinstance(eyedata.index, dtype) for dtype in allowed_index_dtypes):
        raise TypeError(f'eyedata.index must be one of {allowed_index_dtypes} not {type(eyedata.index)}')

    if not all(col in eyedata.columns for col in ('eyeh', 'eyev')):
        raise ValueError("Eyedata must contain columns ['eyeh', 'eyev']")

    diff = eyedata.diff() * sampling_rate
    diff['radial'] = np.hypot(diff['eyeh'], diff['eyev'])

    if method == 'radial':
        velocity = diff['radial']
    elif method == 'horizontal':
        velocity = diff['eyeh']
    elif method == 'vertical':
        velocity = diff['eyev']
    else:
        raise ValueError(f"Method must be one of ['radial', 'horizontal', 'vertical'] not {method}")

    velocity.rename('velocity')
    saccade = velocity.abs() > velocity_threshold

    onset = saccade & (saccade != saccade.shift()) & ~saccade.shift().isna()
    offset = ~saccade & (saccade != saccade.shift()) & ~saccade.shift().isna()

    onset = saccade[onset].index
    offset = saccade[offset].index
    
    if onset.size != offset.size:
        if onset.size - offset.size == 1:
            onset = onset[:-1] # exclude last saccade
        else:
            raise ValueError(
                f"Number of onsets {onset.size} and offsets {offset.size} \
                must be the same or differ by 1 (edge case where the last \
                offset does not occur within the trace)")

    saccade_data = pd.DataFrame({
        'onset_t': onset,
        'offset_t': offset
    })
    
    saccade_data['delta_t'] = saccade_data['offset_t'] - saccade_data['onset_t']

    if duration_threshold is not None:
        saccade_data = saccade_data[saccade_data['delta_t'] > duration_threshold]
    
    def get_saccade_metrics(saccade):
        times = {'onset': saccade.onset_t, 'offset': saccade.offset_t}
        components = {'x':'eyeh', 'y':'eyev'}
        data = {
            f"{time_name}_{component}": eyedata.loc[time, component_var_name]
            for (time_name, time), (component, component_var_name) in product(times.items(),components.items())
        }
        data['peak_radial_velocity'] = diff.loc[slice(saccade.onset_t, saccade.offset_t), 'radial'].max()
        return pd.Series(data)
    
    if len(saccade_data) > 0:
        saccade_data = saccade_data.join(
            saccade_data.apply(get_saccade_metrics, axis=1)
        )
    
        saccade_data['delta_x'] = saccade_data['offset_x'] - saccade_data['onset_x']
        saccade_data['delta_y'] = saccade_data['offset_y'] - saccade_data['onset_y']

        saccade_data['amplitude'] = np.hypot(saccade_data['delta_x'], saccade_data['delta_y'])
        saccade_data['direction'] = np.arctan2(saccade_data['delta_y'], saccade_data['delta_x'])
        saccade_data['duration'] = saccade_data['delta_t'].dt.total_seconds()*1e3

        if hasattr(saccade_data['onset_t'], 'dt'):
            saccade_data['latency'] = saccade_data['onset_t'].dt.total_seconds()*1e3

    saccade_data.reset_index(drop=True, inplace = True)

    return saccade_data