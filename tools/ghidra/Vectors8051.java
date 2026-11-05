// Seed disassembly at 8051 reset/interrupt vectors of a raw code bank.
import ghidra.app.script.GhidraScript;
import ghidra.app.cmd.disassemble.DisassembleCommand;
import ghidra.program.model.address.Address;
public class Vectors8051 extends GhidraScript {
    @Override public void run() throws Exception {
        for (int v = 0; v <= 0x6b; v += (v == 0 ? 3 : 8)) {
            Address a = toAddr("CODE:" + Integer.toHexString(v));
            new DisassembleCommand(a, null, true).applyTo(currentProgram, monitor);
            if (getFunctionAt(a) == null) createFunction(a, null);
        }
    }
}
