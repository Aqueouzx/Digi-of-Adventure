// Digilent Nexys 4 DDR: 100 MHz -> debounced gamepad -> USB/UART, 115200 8N1.
module nexys_pad(input CLK100MHZ, BTNL, BTNR, BTNU, BTNC, BTND, UART_TXD_IN,
                 output UART_RXD_OUT, output [7:0] AN, output [6:0] SEG, output DP);
    wire [4:0] raw = {BTND, BTNC, BTNU, BTNR, BTNL};
    (* ASYNC_REG = "TRUE" *) reg [4:0] sync1=0, sync2=0;
    reg [4:0] sample1=0, sample2=0, stable=0;
    reg [16:0] sample_div=0;
    reg [19:0] report_div=0;
    reg [9:0] shift=10'h3ff;
    reg [3:0] bits_left=0;
    reg [9:0] baud_div=0;
    assign UART_RXD_OUT=shift[0];
    always @(posedge CLK100MHZ) begin
        sync1 <= raw;
        sync2 <= sync1;
        if (sample_div == 99999) begin
            sample_div <= 0;
            sample1 <= sync2;
            sample2 <= sample1;
            stable <= (stable & (sync2 | sample1 | sample2)) | (sync2 & sample1 & sample2);
        end else sample_div <= sample_div + 1'b1;
        if (report_div == 499999) begin // 200 full-state reports per second
            report_div <= 0;
            shift <= {1'b1, 3'b101, stable, 1'b0};
            bits_left <= 10;
            baud_div <= 0;
        end else begin
            report_div <= report_div + 1'b1;
            if (bits_left != 0) begin
                if (baud_div == 867) begin
                    baud_div <= 0;
                    shift <= {1'b1,shift[9:1]};
                    bits_left <= bits_left - 1'b1;
                end else baud_div <= baud_div + 1'b1;
            end
        end
    end
    // The host sends 0xD0 (blank) or 0xD1..0xD5. The game owns the clock.
    (* ASYNC_REG = "TRUE" *) reg rx_meta=1, rx=1;
    reg [3:0] rx_state=0;
    reg [9:0] wait_clocks=0;
    reg [7:0] received=0;
    reg [2:0] digit=0;
    reg [26:0] silence=0;
    reg [6:0] segments;
    assign SEG = segments; // SEG[6:0] = g,f,e,d,c,b,a (active low)
    assign AN = (digit==0) ? 8'hff : 8'hfe;
    assign DP = 1'b1;
    always @* begin
        case (digit)
            1: segments=7'b1111001;
            2: segments=7'b0100100;
            3: segments=7'b0110000;
            4: segments=7'b0011001;
            5: segments=7'b0010010;
            default: segments=7'b1111111;
        endcase
    end
    always @(posedge CLK100MHZ) begin
        rx_meta <= UART_TXD_IN;
        rx <= rx_meta;
        if (silence < 100000000)
            silence <= silence + 1'b1;
        else
            digit <= 0;
        if (rx_state==0) begin
            if (!rx) begin
                rx_state <= 1;
                wait_clocks <= 433; // sample centre of start bit
            end
        end else if (wait_clocks!=0) begin
            wait_clocks <= wait_clocks - 1'b1;
        end else begin
            wait_clocks <= 867;
            case (rx_state)
                1: rx_state <= rx ? 0 : 2;
                10: begin // centre of stop bit
                    rx_state <= 0;
                    if (rx && received[7:4]==4'hd && received[3:0]<=5) begin
                        digit <= received[2:0];
                        silence <= 0;
                    end
                end
                default: begin // states 2..9 receive LSB first
                    received <= {rx, received[7:1]};
                    rx_state <= rx_state + 1'b1;
                end
            endcase
        end
    end
endmodule
