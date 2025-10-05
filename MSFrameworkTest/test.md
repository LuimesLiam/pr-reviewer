Mermaid flowchart:
flowchart TD
dispatcher["dispatcher (Start)"];
average["average"];
summation["summation"];
aggregator["aggregator"];
fan_in**aggregator**01858188((fan-in))
average --> fan_in**aggregator**01858188;
summation --> fan_in**aggregator**01858188;
fan_in**aggregator**01858188 --> aggregator;
dispatcher --> average;
dispatcher --> summation;
