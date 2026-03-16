import React, { useState, useEffect } from 'react';
import { XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine, ReferenceArea, Bar, ComposedChart, Area } from 'recharts';
import { HourlyData } from '../types';
import { periodToTimeString, periodToTimeRange } from '../utils/timeUtils';
import { DataResolution } from '../hooks/useUserPreferences';

interface BatteryLevelChartProps {
  hourlyData: HourlyData[];
  tomorrowData?: HourlyData[] | null;
  settings: any; // Adjust type as needed
  resolution: DataResolution;
}

export const BatteryLevelChart: React.FC<BatteryLevelChartProps> = ({ hourlyData, tomorrowData, resolution }) => {
  // Reactive dark mode detection — observes class changes on <html> to match Tailwind's 'class' strategy
  const [isDarkMode, setIsDarkMode] = useState(
    document.documentElement.classList.contains('dark')
  );

  useEffect(() => {
    const observer = new MutationObserver(() => {
      setIsDarkMode(document.documentElement.classList.contains('dark'));
    });
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
    return () => observer.disconnect();
  }, []);

  const colors = {
    grid: isDarkMode ? '#374151' : '#e5e7eb',
    text: isDarkMode ? '#d1d5db' : '#374151',
    background: isDarkMode ? '#1f2937' : '#ffffff',
    tooltip: isDarkMode ? '#374151' : '#ffffff',
    tooltipBorder: isDarkMode ? '#4b5563' : '#d1d5db'
  };

  // Extract values from FormattedValue objects or fallback to raw numbers
  const getValue = (field: any) => {
    if (typeof field === 'object' && field?.value !== undefined) {
      return field.value;
    }
    return field || 0;
  };

  // Transform daily view data to chart format
  const chartData = hourlyData.map((hour, index) => {
    // Check for missing keys and provide warnings
    if (hour.batteryAction === undefined) {
      console.warn(`Missing key: batteryAction at index ${index}`);
    }
    if (hour.batterySocEnd === undefined) {
      console.warn(`Missing key: batterySocEnd at index ${index}`);
    }
    if (hour.dataSource === undefined) {
      console.warn(`Missing key: dataSource at index ${index}`);
    }

    if (hour.batteryAction === undefined) {
      throw new Error(`MISSING DATA: batteryAction is required but missing at index ${index}`);
    }
    const batteryAction = getValue(hour.batteryAction);
    const rawSoc = getValue(hour.batterySocEnd);
    const isActual = hour.dataSource === 'actual';
    // Treat zero SOC on predicted periods as missing data
    const batterySocPercent = (rawSoc === 0 && !isActual) ? null : rawSoc;
    const periodNum = hour.period ?? index;
    if (hour.dataSource === undefined) {
      throw new Error(`MISSING DATA: dataSource is required but missing at index ${index}`);
    }
    const dataSource = hour.dataSource;

    // Calculate x-axis position (start of period)
    let xPosition: number;
    if (resolution === 'quarter-hourly') {
      xPosition = periodNum / 4;
    } else {
      xPosition = periodNum;
    }

    return {
      hour: xPosition,
      periodNum,
      hourLabel: periodToTimeString(periodNum, resolution),
      batterySocPercent: batterySocPercent,
      action: batteryAction,
      dataSource: dataSource,
      isActual: dataSource === 'actual',
      isPredicted: dataSource === 'predicted',
      isTomorrow: false,
      // Include FormattedValue objects for tooltip
      batterySocEndFormatted: hour.batterySocEnd,
      batteryActionFormatted: hour.batteryAction
    };
  });

  // Append tomorrow's data with hour offset 24+
  const hasTomorrowData = tomorrowData && tomorrowData.length > 0;
  if (hasTomorrowData) {
    for (const [idx, hour] of tomorrowData.entries()) {
      if (hour.batteryAction === undefined) {
        console.warn(`Missing key: batteryAction in tomorrow data at index ${idx}`);
        continue;
      }
      const batteryAction = getValue(hour.batteryAction);
      const rawSocTmrw = getValue(hour.batterySocEnd);
      const batterySocPercent = rawSocTmrw === 0 ? null : rawSocTmrw;
      // Normalize period numbers: API may return 96-191 (continuation from today) or 0-95
      const rawPeriodNum = hour.period ?? idx;
      const tomorrowPeriodsPerDay = resolution === 'quarter-hourly' ? 96 : 24;
      const periodNum = rawPeriodNum >= tomorrowPeriodsPerDay ? rawPeriodNum - tomorrowPeriodsPerDay : rawPeriodNum;
      const dataSource = hour.dataSource ?? 'predicted';

      let xPosition: number;
      if (resolution === 'quarter-hourly') {
        xPosition = 24 + periodNum / 4;
      } else {
        xPosition = 24 + periodNum;
      }

      chartData.push({
        hour: xPosition,
        periodNum,
        hourLabel: periodToTimeString(periodNum, resolution),
        batterySocPercent,
        action: batteryAction,
        dataSource,
        isActual: false,
        isPredicted: true,
        isTomorrow: true,
        batterySocEndFormatted: hour.batterySocEnd,
        batteryActionFormatted: hour.batteryAction
      });
    }
  }

  // Compute max hour for X-axis (add 1 for stepAfter to render last period)
  const maxHourValue = hasTomorrowData
    ? Math.ceil(Math.max(...chartData.map(d => d.hour))) + 1
    : 24;
  const xAxisTicks = Array.from({ length: maxHourValue + 1 }, (_, i) => i);

  const maxAction = Math.max(...chartData.map(d => Math.abs(d.action || 0)), 1);

  // Find predicted hours range for background shading
  const firstPredictedIdx = chartData.findIndex(d => !d.isActual && !d.isTomorrow);
  const lastTodayIdx = chartData.findIndex(d => d.isTomorrow);
  const firstPredictedHour = firstPredictedIdx > -1 ? chartData[firstPredictedIdx].hour : null;
  const lastTodayHour = lastTodayIdx > -1 ? chartData[lastTodayIdx - 1]?.hour : maxHourValue;

  return (
    <div className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow">
      <div style={{ width: '100%', height: '400px' }}>
        <ResponsiveContainer>
          <ComposedChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 60 }}>
            <CartesianGrid strokeDasharray="5 5" stroke={colors.grid} strokeOpacity={0.3} strokeWidth={0.5} />
            <XAxis
              dataKey="hour"
              type="number"
              interval={0}
              stroke={colors.text}
              tick={{ fontSize: 12 }}
              domain={[0, maxHourValue]}
              ticks={xAxisTicks}
              label={{ value: 'Hour of Day', position: 'insideBottom', offset: -10 }}
              tickFormatter={(hour: number) => {
                return (Math.floor(hour) % 24).toString().padStart(2, '0');
              }}
            />
            
            {/* Left Y-axis for Battery SOC (%) */}
            <YAxis 
              yAxisId="left" 
              stroke={colors.text}
              domain={[0, 100]} 
              tick={{ fontSize: 12 }}
              tickFormatter={(value) => `${Math.round(value)}%`}
              label={{ 
                value: 'Battery SOC (%)', 
                angle: -90, 
                position: 'insideLeft', 
                style: { textAnchor: 'middle', dominantBaseline: 'central' }
              }}
            />
            
            {/* Right Y-axis for Battery Actions (kWh) */}
            <YAxis
              yAxisId="action"
              orientation="right"
              stroke={colors.text}
              domain={[-maxAction * 1.2, maxAction * 1.2]}
              tick={{ fontSize: 12 }}
              tickFormatter={(value) => value.toLocaleString('sv-SE', {minimumFractionDigits: 1, maximumFractionDigits: 1})}
              label={{
                value: 'Battery Action (kWh)',
                angle: 90,
                position: 'insideRight',
                style: { textAnchor: 'middle', dominantBaseline: 'central' }
              }}
            />
            
            <Tooltip 
              contentStyle={{
                backgroundColor: colors.tooltip,
                border: `1px solid ${colors.tooltipBorder}`,
                borderRadius: '8px',
                color: colors.text
              }}
              formatter={(value, name, props) => {
                const payload = props?.payload;
                if (name === 'Battery SOC') return [payload?.batterySocEndFormatted?.text || 'N/A', 'Battery SOC'];
                if (name === 'Battery Action') {
                  const actionValue = Number(value);
                  const formattedText = payload?.batteryActionFormatted?.text || 'N/A';
                  if (actionValue >= 0) {
                    return [formattedText, 'Battery Charging'];
                  } else {
                    return [formattedText, 'Battery Discharging'];
                  }
                }
                return ['N/A', name];
              }}
              labelFormatter={(_label, payload) => {
                // Get period index from the first data point in tooltip
                if (payload && payload.length > 0) {
                  const periodNum = payload[0].payload.periodNum;
                  const isTmrw = payload[0].payload.isTomorrow;
                  const timeRange = periodToTimeRange(periodNum, resolution);
                  return isTmrw ? `Tomorrow ${timeRange}` : timeRange;
                }
                return '';
              }}
              labelStyle={{ color: colors.text }}
            />
            
            <ReferenceLine yAxisId="action" y={0} stroke={colors.grid} strokeDasharray="2 2" />

            {/* Hourly vertical grid lines - extend for tomorrow data */}
            {Array.from({ length: maxHourValue + 1 }, (_, i) => (
              <ReferenceLine
                key={`hour-${i}`}
                x={i}
                yAxisId="left"
                stroke={colors.grid}
                strokeOpacity={0.3}
                strokeWidth={0.5}
                strokeDasharray="5 5"
              />
            ))}

            
            <Area
              yAxisId="left"
              type="monotone"
              dataKey="batterySocPercent"
              stroke="#16a34a"
              strokeWidth={2}
              fill="#16a34a"
              fillOpacity={0.1}
              name="Battery SOC"
            />

            {/* Overlay for predicted hours (today only) */}
            {firstPredictedHour !== null && (
              <ReferenceArea
                yAxisId="left"
                x1={firstPredictedHour}
                x2={lastTodayHour}
                fill={isDarkMode ? 'rgba(120,120,120,0.12)' : 'rgba(120,120,120,0.10)'}
                ifOverflow="hidden"
              />
            )}
            
            <Bar 
              yAxisId="action" 
              dataKey="action" 
              name="Battery Action" 
              radius={[2, 2, 2, 2]}
              shape={(props: any) => {
                const { payload, x, y, width, height } = props;
                const action = payload.action || 0;
                const isActual = payload.isActual;
                const isTmrw = payload.isTomorrow;

                const fillColor = action >= 0 ? '#16a34a' : '#dc2626';
                const opacity = isTmrw ? 0.35 : (isActual ? 0.9 : 0.6);
                
                return (
                  <rect 
                    x={x} 
                    y={action >= 0 ? y : y + height} 
                    width={width} 
                    height={Math.abs(height)} 
                    fill={fillColor}
                    fillOpacity={opacity}
                    rx={2}
                    ry={2}
                  />
                );
              }}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {/* Custom Legend */}
      <div className="flex flex-wrap justify-center gap-6 mt-1 text-sm">
        <div className="flex items-center">
          <div className="w-4 h-3 rounded mr-2" style={{ backgroundColor: '#16a34a' }}></div>
          <span className="text-gray-700 dark:text-gray-300">Battery SOC</span>
        </div>
        <div className="flex items-center">
          <div className="w-4 h-3 rounded mr-2" style={{ backgroundColor: '#16a34a' }}></div>
          <span className="text-gray-700 dark:text-gray-300">Battery Charging</span>
        </div>
        <div className="flex items-center">
          <div className="w-4 h-3 rounded mr-2" style={{ backgroundColor: '#dc2626' }}></div>
          <span className="text-gray-700 dark:text-gray-300">Battery Discharging</span>
        </div>
        {hasTomorrowData && (
          <div className="flex items-center text-xs text-gray-600 dark:text-gray-400">
            <div className="w-4 h-3 rounded mr-1" style={{ backgroundColor: '#16a34a', opacity: 0.35 }}></div>
            <span>Tomorrow</span>
          </div>
        )}
      </div>
    </div>
  );
};