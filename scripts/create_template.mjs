// Run with the bundled Node runtime; uses the external artifact-tool junction.
import fs from 'node:fs/promises';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';

const out='outputs/01a0e82b-ebf7-7af3-8aa0-c14e14564970';
await fs.mkdir(out,{recursive:true});
await fs.mkdir('examples',{recursive:true});
const wb=Workbook.create();
const gp=wb.worksheets.add('GP');
const notes=wb.worksheets.add('Инструкция');
const headers=['player_a','player_b','table',...Array.from({length:9},(_,i)=>`M${i}`)];
const rows=[];
for(let a=0;a<3;a++) for(let b=0;b<3;b++) for(let t=0;t<3;t++)
  rows.push([a,b,t,...Array(9).fill(null)]);
gp.getRange('A1:L28').values=[headers,...rows];
gp.showGridLines=false;
gp.getRange('A1:L28').format.font={name:'Arial',size:11};
gp.getRange('A1:L28').format.rowHeight=24;
gp.getRange('A1:C28').format.columnWidth=14;
gp.getRange('D1:L28').format.columnWidth=10;
gp.getRange('A1:L1').format={fill:'#24374A',font:{name:'Arial',size:11,bold:true,color:'#FFFFFF'}};
gp.getRange('D2:L28').format.fill='#FFF3CC';
gp.getRange('D2:L28').setNumberFormat('0.00');
gp.getRange('A2:C28').setNumberFormat('0');
gp.getRange('A1:L1').format.horizontalAlignment='center';
gp.freezePanes.freezeRows(1);
gp.freezePanes.freezeColumns(3);
gp.getRange('D2:L28').conditionalFormats.add('cellIs',{
  operator:'notBetween',formula:[0,20],format:{fill:'#FCE1DE',font:{color:'#A12622'}}
});
for(const row of [5,8,11,14,17,20,23,26])
  gp.getRange(`A${row}:L${row}`).format.borders={top:{style:'thin',color:'#B9C4CF'}};

notes.showGridLines=false;
notes.getRange('A1:F30').format.font={name:'Arial',size:11};
notes.getRange('A1:F30').format.columnWidth=22;
notes.getRange('A1:F30').format.rowHeight=25;
notes.getRange('A2').values=[['WTC 3×3 — ожидаемые GP']];
notes.getRange('A2').format.font={name:'Arial',size:16,bold:true,color:'#24374A'};
const instructions=[
  'Заполните 243 жёлтые ячейки на листе GP: ожидаемые очки команды A, от 0 до 20.',
  'Одна строка — игрок A, игрок B и стол. Девять столбцов M0–M8 — миссии.',
  'Дробные оценки разрешены. Пустая ячейка означает «не заполнено», а не ноль.',
  'Например: 12,5 означает 12,5 GP для A и 7,5 GP для B (в CSV используйте точку).',
  'Сохраните только лист GP как CSV UTF-8: разделитель — запятая, дроби — с точкой.',
  'Не меняйте заголовки и числовые ID на листе GP. Названия можно записать ниже.',
  'Команда A остаётся A при обеих ролях. Не переворачивайте оценки для защитника.'
];
notes.getRange('A4:A10').values=instructions.map(x=>[x]);
notes.getRange('A12:F12').values=[['Категория','ID','Название',null,null,null]];
notes.getRange('A12:C12').format={fill:'#24374A',font:{name:'Arial',size:11,color:'#FFFFFF',bold:true}};
const entities=[];
for(const kind of ['Игрок A','Игрок B','Стол']) for(let i=0;i<3;i++) entities.push([kind,i,null]);
for(let i=0;i<9;i++) entities.push(['Миссия',`M${i}`,null]);
notes.getRange('A13:C30').values=entities;
notes.getRange('C13:C30').format.fill='#FFF3CC';
notes.getRange('C13:C30').format.columnWidth=35;

// Probe missing versus zero without filling the delivered template.
if(gp.getRange('D2').values[0][0]!==null) throw new Error('Blank input was converted to zero');
gp.getRange('D2').values=[[0]];
if(gp.getRange('D2').values[0][0]!==0) throw new Error('Zero lost');
gp.getRange('D2').values=[[null]];
wb.recalculate();
console.log((await wb.inspect({kind:'table',range:'GP!A1:L4',include:'values,formulas',tableMaxRows:4,tableMaxCols:12})).ndjson);
console.log((await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:20}})).ndjson);
for(const [sheetName,range,name] of [['GP','A1:L28','gp_preview'],['Инструкция','A1:F30','instructions_preview']]) {
  const blob=await wb.render({sheetName,range,scale:1.5,format:'png'});
  await fs.writeFile(`${out}/${name}.png`,new Uint8Array(await blob.arrayBuffer()));
}
await (await SpreadsheetFile.exportXlsx(wb)).save(`${out}/gp_template.xlsx`);
await fs.writeFile('examples/gp_template.csv',[headers,...rows].map(r=>r.map(x=>x??'').join(',')).join('\n')+'\n');
console.log(`Saved ${out}/gp_template.xlsx and examples/gp_template.csv`);
