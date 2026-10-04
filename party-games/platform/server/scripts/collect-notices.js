// Archive notices from the installed runtime tree for distributable server bundles.
const fs=require('fs');
const path=require('path');
const root=path.resolve(__dirname,'../node_modules');
const lock=require('../package-lock.json');
let output='# Server dependency notices\n\nGenerated from package-lock.json and installed license files.\n';
const missing=[];
for(const [relative,metadata] of Object.entries(lock.packages)) {
  if(!relative || metadata.dev)continue;
  const directory=path.resolve(__dirname,'..',relative);
  const pkg=JSON.parse(fs.readFileSync(path.join(directory,'package.json'),'utf8'));
  const files=fs.readdirSync(directory).filter(name=>/^(licen[cs]e|copying|notice)([._-].*)?$/i.test(name)&&fs.statSync(path.join(directory,name)).isFile());
  output+=`\n## ${pkg.name} ${pkg.version}\n\nDeclared license: ${JSON.stringify(pkg.license || 'unspecified')}\n`;
  if(!files.length)missing.push(pkg.name);
  for(const file of files)output+=`\n${file}:\n\n\`\`\`text\n${fs.readFileSync(path.join(directory,file),'utf8').trim()}\n\`\`\`\n`;
}
fs.writeFileSync(path.resolve(__dirname,'../THIRD_PARTY_NOTICES.md'),output);
if(missing.length){console.error('Missing license text: '+missing.join(', '));process.exitCode=1;}
else console.log('Archived runtime dependency license notices.');
