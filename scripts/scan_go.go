// AST-only inventory: never loads or initializes either project's packages.
package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"go/ast"
	"go/format"
	"go/parser"
	"go/token"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"unicode"
)

type M = map[string]any

func main() {
	if len(os.Args) != 4 {
		panic("usage: scan_go <project-root> <project-id> <output>")
	}
	root, repo, out := os.Args[1], os.Args[2], os.Args[3]
	result := M{"schema": 1, "files": []M{}, "errors": []M{}}
	files := []M{}
	problems := []M{}
	{
		err := filepath.WalkDir(root, func(path string, d os.DirEntry, err error) error {
			if err != nil {
				return err
			}
			if d.IsDir() {
				if d.Name() == ".git" || d.Name() == "vendor" || d.Name() == "node_modules" {
					return filepath.SkipDir
				}
				return nil
			}
			if d.Type()&os.ModeSymlink != 0 {
				return nil
			}
			if !strings.HasSuffix(path, "_test.go") {
				return nil
			}
			rel, _ := filepath.Rel(root, path)
			rel = filepath.ToSlash(rel)
			src, e := os.ReadFile(path)
			if e != nil {
				return e
			}
			fs := token.NewFileSet()
			f, e := parser.ParseFile(fs, path, src, parser.ParseComments|parser.AllErrors)
			if e != nil {
				problems = append(problems, M{"repo": repo, "path": rel, "error": e.Error()})
				return nil
			}
			code := func(n ast.Node) string {
				if n == nil {
					return ""
				}
				a, b := fs.Position(n.Pos()).Offset, fs.Position(n.End()).Offset
				return string(src[a:b])
			}
			pos := func(n ast.Node) int { return fs.Position(n.Pos()).Line }
			formatted := func(n ast.Node) string { var b bytes.Buffer; _ = format.Node(&b, fs, n); return b.String() }
			imports := []string{}
			testingAlias := "testing"
			tags := []string{}
			for _, im := range f.Imports {
				v, _ := strconv.Unquote(im.Path.Value)
				imports = append(imports, v)
				if v == "testing" && im.Name != nil {
					testingAlias = im.Name.Name
				}
			}
			for _, c := range f.Comments {
				for _, l := range c.List {
					if strings.HasPrefix(l.Text, "//go:build") || strings.HasPrefix(l.Text, "// +build") {
						tags = append(tags, l.Text)
					}
				}
			}
			decls := []M{}
			support := []string{}
			globals := []M{}
			for _, decl := range f.Decls {
				fn, ok := decl.(*ast.FuncDecl)
				if !ok {
					if gd, isGen := decl.(*ast.GenDecl); isGen {
						support = append(support, formatted(decl))
						if gd.Tok == token.VAR || gd.Tok == token.CONST {
							for _, spec := range gd.Specs {
								if vs, ok := spec.(*ast.ValueSpec); ok {
									for _, name := range vs.Names {
										globals = append(globals, M{"name": name.Name, "line": pos(vs), "code": code(vs)})
									}
								}
							}
						}
					}
					continue
				}
				kind := "helper"
				name := fn.Name.Name
				valid := func(typ string) bool {
					if fn.Recv != nil || fn.Type.Params.NumFields() != 1 || fn.Type.Results != nil {
						return false
					}
					p, ok := fn.Type.Params.List[0].Type.(*ast.StarExpr)
					if !ok {
						return false
					}
					s, ok := p.X.(*ast.SelectorExpr)
					if !ok {
						return false
					}
					x, ok := s.X.(*ast.Ident)
					return ok && x.Name == testingAlias && s.Sel.Name == typ
				}
				prefix := func(p string) bool {
					tail := strings.TrimPrefix(name, p)
					return strings.HasPrefix(name, p) && (tail == "" || !unicode.IsLower([]rune(tail)[0]))
				}
				if name == "TestMain" && valid("M") {
					kind = "TestMain"
				} else if prefix("Test") && valid("T") {
					kind = "test"
				} else if prefix("Fuzz") && valid("F") {
					kind = "fuzz"
				} else if prefix("Benchmark") && valid("B") {
					kind = "benchmark"
				} else if prefix("Example") && fn.Recv == nil && fn.Type.Params.NumFields() == 0 {
					kind = "example"
				} else if name == "init" {
					kind = "init"
				}
				receiver := ""
				if fn.Recv != nil {
					receiver = code(fn.Recv)
				}
				assertions := []M{}
				runs := []M{}
				calls := []string{}
				inputs := []string{}
				branches := []M{}
				tables := []M{}
				seenCall := map[string]bool{}
				ast.Inspect(fn.Body, func(n ast.Node) bool {
					switch n := n.(type) {
					case *ast.CallExpr:
						callee := code(n.Fun)
						if !seenCall[callee] {
							calls = append(calls, callee)
							seenCall[callee] = true
						}
						if sel, ok := n.Fun.(*ast.SelectorExpr); ok {
							x := code(sel.X)
							m := sel.Sel.Name
							if x == "assert" || x == "require" || strings.HasPrefix(x, "assert.") || strings.HasPrefix(x, "require.") || ((x == "t" || x == "s" || strings.HasSuffix(x, ".T()")) && (strings.HasPrefix(m, "Fatal") || strings.HasPrefix(m, "Error") || strings.HasPrefix(m, "Skip"))) {
								arguments := []string{}
								for _, arg := range n.Args {
									arguments = append(arguments, code(arg))
								}
								assertions = append(assertions, M{"line": pos(n), "code": code(n), "method": m, "receiver": x, "arguments": arguments})
							}
							if m == "Run" && len(n.Args) >= 2 {
								if _, ok := n.Args[1].(*ast.FuncLit); ok {
									nameExpr := code(n.Args[0])
									lit := ""
									if l, ok := n.Args[0].(*ast.BasicLit); ok && l.Kind == token.STRING {
										lit, _ = strconv.Unquote(l.Value)
									}
									runs = append(runs, M{"line": pos(n), "name": lit, "expression": nameExpr, "code": code(n)})
								}
							}
						}
					case *ast.BasicLit:
						if n.Kind == token.STRING || n.Kind == token.INT || n.Kind == token.FLOAT {
							if len(inputs) < 120 {
								inputs = append(inputs, code(n))
							}
						}
					case *ast.IfStmt:
						branches = append(branches, M{"line": pos(n), "condition": code(n.Cond), "code": code(n)})
					case *ast.CompositeLit:
						isTable := false
						switch n.Type.(type) {
						case *ast.ArrayType, *ast.MapType:
							isTable = true
						}
						if !isTable || len(n.Elts) == 0 {
							return true
						}
						structRows := 0
						for _, e := range n.Elts {
							if _, ok := e.(*ast.CompositeLit); ok {
								structRows++
							}
						}
						if structRows > 0 {
							rows := []M{}
							for i, e := range n.Elts {
								nm := ""
								if cl, ok := e.(*ast.CompositeLit); ok {
									for j, v := range cl.Elts {
										if kv, ok := v.(*ast.KeyValueExpr); ok {
											key := code(kv.Key)
											if key == "name" || key == "Name" || key == "desc" {
												if l, ok := kv.Value.(*ast.BasicLit); ok && l.Kind == token.STRING {
													nm, _ = strconv.Unquote(l.Value)
												}
											}
										} else if j == 0 {
											if l, ok := v.(*ast.BasicLit); ok && l.Kind == token.STRING {
												nm, _ = strconv.Unquote(l.Value)
											}
										}
									}
								}
								if nm == "" {
									nm = fmt.Sprintf("row[%d]", i)
								}
								rows = append(rows, M{"name": nm, "line": pos(e), "code": code(e)})
							}
							tables = append(tables, M{"line": pos(n), "rows": rows, "type": code(n.Type)})
						}
					}
					return true
				})
				comment := ""
				if fn.Doc != nil {
					comment = fn.Doc.Text()
				}
				entry := M{"name": name, "kind": kind, "receiver": receiver, "line": pos(fn), "endLine": fs.Position(fn.End()).Line, "code": code(fn), "body": formatted(fn.Body), "comment": comment, "assertions": assertions, "runs": runs, "tables": tables, "calls": calls, "inputs": inputs, "branches": branches}
				decls = append(decls, entry)
				if kind == "helper" || kind == "init" || kind == "TestMain" {
					support = append(support, formatted(fn))
				}
			}
			files = append(files, M{"repo": repo, "path": rel, "package": f.Name.Name, "imports": imports, "tags": tags, "decls": decls, "support": strings.Join(support, "\n"), "globals": globals, "source": string(src)})
			return nil
		})
		if err != nil {
			panic(err)
		}
	}
	result["files"] = files
	result["errors"] = problems
	b, e := json.Marshal(result)
	if e != nil {
		panic(e)
	}
	if e = os.WriteFile(out, b, 0644); e != nil {
		panic(e)
	}
	fmt.Printf("AST files=%d parse_errors=%d\n", len(files), len(problems))
}
