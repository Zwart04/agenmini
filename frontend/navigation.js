// Keep four pages: feature sections are part of their parent page and always visible.
for(const [child,parent] of Object.entries(pageSections)){
 const source=$('#v-'+child+' .page-in'),target=$('#v-'+parent+' .page-in');
 const section=document.createElement('section');section.id='section-'+child;section.className='merged-section';
 source.querySelectorAll('.section-tabs').forEach(n=>n.remove());
 while(source.firstChild)section.append(source.firstChild);
 target.append(section);$('#v-'+child).remove();
}
$$('.section-tabs').forEach(n=>n.remove());
start();
