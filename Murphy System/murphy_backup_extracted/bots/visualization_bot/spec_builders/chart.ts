// Minimal Vega-Lite–style spec builder
export function makeChartSpec(task:string, data:any, style:any): any {
  // Infer mark: 'bar' if small categorical; else 'line'
  const values = Array.isArray(data?.values) ? data.values : (Array.isArray(data) ? data : []);
  const sample = values[0] || {};
  const fields = Object.keys(sample);
  const numerics = fields.filter(f => typeof sample[f] === 'number');
  const times = fields.filter(f => /time|date/i.test(f));
  const categories = fields.filter(f => typeof sample[f] === 'string');

  const xField = times[0] || categories[0] || fields[0] || 'x';
  const yField = numerics[0] || fields.find(f=>f!=='x' && typeof sample[f]==='number') || 'y';

  const inferredBar = categories.length>0 && numerics.length>0 && !times.length;
  const mark = inferredBar ? 'bar' : 'line';

  const spec:any = {
    $schema: 'https://vega.github.io/schema/vega-lite/v5.json',
    description: task,
    data: { values },
    mark,
    encoding: {
      x: { field: xField, type: inferredBar ? 'nominal' : (times.length ? 'temporal':'quantitative') },
      y: { field: yField, type: 'quantitative', scale: { zero: inferredBar ? true : false } }
    },
    config: {}
  };
  if (style?.show_grid) {
    spec.config.axis = { grid: true };
  }
  if (style?.colorblind_safe) {
    spec.config.range = { category: ['#0072B2','#009E73','#D55E00','#CC79A7','#56B4E9','#F0E442'] };
  }
  return spec;
}
