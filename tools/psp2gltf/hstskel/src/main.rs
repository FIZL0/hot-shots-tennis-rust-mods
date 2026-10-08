//! hstskel <file.MDL> — print HST's node tree (index, parent, name, bind translation) as TSV.
fn main() {
    let p = std::env::args().nth(1).expect("usage: hstskel file.MDL");
    let m = hst_data::mdl::parse(&std::fs::read(p).unwrap()).unwrap();
    for i in 0..m.node_count {
        let b = m.node_bind[i];
        let par = m.node_parent[i].map(|x| x as i64).unwrap_or(-1);
        println!("{i}\t{par}\t{}\t{:.3}\t{:.3}\t{:.3}\t{:?}", m.node_names[i], b[3][0], b[3][1], b[3][2], b);
    }
}
