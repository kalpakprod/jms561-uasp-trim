// Decompile the 8051 functions that contain the given CPU addresses.
// Script args: <output file> <hex addr>... Each address is disassembled first; when no
// function contains it, a function is created there (continuation targets reached only
// through the RAM 0x6C/0x6D pointer are invisible to auto-analysis).
// @category JMS561
import ghidra.app.cmd.disassemble.DisassembleCommand;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import java.io.PrintWriter;

public class DecompileAt extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        DecompInterface di = new DecompInterface();
        di.openProgram(currentProgram);
        try (PrintWriter out = new PrintWriter(args[0])) {
            for (int i = 1; i < args.length; i++) {
                Address a = toAddr(Long.parseLong(args[i].replace("0x", ""), 16));
                new DisassembleCommand(a, null, true).applyTo(currentProgram, monitor);
                Function f = getFunctionContaining(a);
                if (f == null) {
                    f = createFunction(a, null);
                }
                out.println("// ===== request " + args[i] + " -> " + (f == null ? "no function" : f.getName() + " @ " + f.getEntryPoint()));
                if (f == null) {
                    continue;
                }
                DecompileResults r = di.decompileFunction(f, 120, monitor);
                out.println(r.decompileCompleted() ? r.getDecompiledFunction().getC() : "// decompile failed: " + r.getErrorMessage());
            }
        }
    }
}
