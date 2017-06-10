/**
 * Created by mm on 2017-05-30.
 */

function Plotter() {
    this.statistics = function (stats) {
        new Highcharts.Chart({
            chart: {
                renderTo: graphStatistics,
                type: 'column'
            },
            title: {
                text: 'Spots statistics'
            },
            xAxis: {
                categories: [
                    'DF Total',
                    'DF 0',
                    'DF 1', //
                    'DF 2', //
                    'DF 3', //
                    'DF 4',
                    'DF 5',
                    'DF 6', //
                    'DF 7',
                    'DF 8',
                    'DF 9',
                    'DF 10', //
                    'DF 11',
                    'DF 12', //
                    'DF 13', //
                    'DF 14', //
                    'DF 15', //
                    'DF 16',
                    'DF 17',
                    'DF 18',
                    'DF 19', //
                    'DF 20',
                    'DF 21',
                    'DF 22', //
                    'DF 23', //
                    'DF 24', //
                    'DF 25', //
                    'DF 26', //
                    'DF 27', //
                    'DF 28', //
                    'DF 29', //
                    'DF 30', //
                    'DF 31'  //
                ],
                crosshair: true
            },
            yAxis: {
                min: 0,
                title: {
                    text: '#'
                }
            },
            tooltip: {
                headerFormat: '<span style="font-size:10px">{point.key}</span><table>',
                pointFormat: '<tr><td style="color:{series.color};padding:0">{series.name}: </td>' +
                '<td style="padding:0"><b>{point.y:.0f} </b></td></tr>',
                footerFormat: '</table>',
                shared: true,
                useHTML: true
            },
            plotOptions: {
                column: {
                    pointPadding: 0.2,
                    borderWidth: 0
                }
            },
            series: [{
                name: 'Downlink format',
                data: stats

            }]
        })
    };

    var gaugeOptions = {
        chart: {
            type: 'solidgauge'
        },

        title: null,

        pane: {
            center: ['50%', '85%'],
            size: '100%',
            startAngle: -90,
            endAngle: 90,
            background: {
                backgroundColor: (Highcharts.theme && Highcharts.theme.background2) || '#EEE',
                innerRadius: '60%',
                outerRadius: '100%',
                shape: 'arc'
            }
        },

        tooltip: {
            enabled: false
        },

        // the value axis
        yAxis: {
            stops: [
                [0.1, '#55BF3B'], // green
                [0.5, '#DDDF0D'], // yellow
                [0.9, '#DF5353'] // red
            ],
            lineWidth: 0,
            minorTickInterval: null,
            tickAmount: 2,
            title: {
                y: -70
            },
            labels: {
                y: 16
            }
        },

        plotOptions: {
            solidgauge: {
                dataLabels: {
                    y: 5,
                    borderWidth: 0,
                    useHTML: true
                }
            }
        }
    };

    var chartSpeed = Highcharts.chart(Highcharts.merge(gaugeOptions, {
        chart: {
            renderTo: graphPreamble
        },
        yAxis: {
            min: 0,
            max: 400,
            title: {
                text: 'Preamble/sec'
            }
        },
        credits: {
            enabled: false
        },
        series: [{
            name: 'Preamble/sec',
            data: [0],
            dataLabels: {
                format: '<div style="text-align:center"><span style="font-size:12px;color:' +
                ((Highcharts.theme && Highcharts.theme.contrastTextColor) || 'black') + '">{y}</span><br/>' +
                '<span style="font-size:8px;color:silver">preamble/sec</span></div>'
            },
            tooltip: {
                valueSuffix: ' preamble/sec'
            }
        }]
    }));

    this.preamble = function (val) {
        chartSpeed.series[0].points[0].update(val);
    };
}